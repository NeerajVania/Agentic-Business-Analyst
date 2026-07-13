"""
backend/api/routes_analyze.py
==============================
Analysis endpoint — triggers the full multi-agent LangGraph pipeline.

  POST /analyze

Frontend consumer
-----------------
  02_analyze.py  →  POST /analyze
    Payload:  { query, dataset_ids, session_id, include_rag }
    Expects:  AnalysisResponse with fields consumed by:
              • kpi_row()         ← kpi_summary
              • agent_badges()    ← active_agents
              • insight_list()    ← insights, trends, recommendations, anomaly_explanations
              • go.Figure(chart)  ← charts  (list of Plotly JSON dicts)
              • st.code()         ← generated_sql, generated_pandas
              • executive_summary (str)
              • processing_time_seconds (float)
              • rag_citations (list[str])
              • errors (list[str])

  03_dashboard.py reads the same result from st.session_state.last_analysis.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger

from agents.graph import run_agent_pipeline
from agents.state import AgentState, safe_state_value
from backend.api.routes_upload import get_dataset_registry
from backend.models.schemas import AnalysisRequest, AnalysisResponse
from memory.redis_memory import get_memory
from rag.pipeline import retrieve_context

router = APIRouter()


async def analysis_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception in /analyze route")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc),
        },
    )


@router.post("", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    """
    Run the full multi-agent analysis pipeline on uploaded datasets.

    Steps
    -----
    1. Validate that all requested dataset_ids exist in the registry.
    2. Optionally retrieve RAG context via semantic search.
    3. Invoke the LangGraph agent pipeline.
    4. Persist result summary to Redis memory.
    5. Return a fully-populated AnalysisResponse.
    """
    registry = get_dataset_registry()
    memory = get_memory()
    start_time = time.time()

    # ── Validate dataset IDs ──────────────────────────────────────────────────
    missing = [d for d in request.dataset_ids if d not in registry]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset IDs not found: {missing}. Upload datasets first via POST /upload/multi.",
        )

    # ── Build DataFrames + schemas dict ───────────────────────────────────────
    dataframes: dict[str, Any] = {}
    schemas: dict[str, Any] = {}
    for ds_id in request.dataset_ids:
        meta = registry[ds_id]
        name = meta["filename"].rsplit(".", 1)[0]
        dataframes[name] = meta["df"]
        schemas[name] = meta["schema"]

    # ── Optional RAG context ──────────────────────────────────────────────────
    rag_context = ""
    rag_citations: list[str] = []
    if request.include_rag:
        try:
            from starlette.concurrency import run_in_threadpool
            rag_context, raw_citations = await run_in_threadpool(retrieve_context, request.query)
            rag_citations = [
                c if isinstance(c, str)
                else f"{c.get('source', 'unknown')} (p{c.get('page_number', '?')}, score={round(float(c.get('relevance_score', 0)), 2)})"
                for c in raw_citations
            ]
        except Exception as exc:
            logger.warning("RAG retrieval failed (non-fatal): {}", exc)

    # ── Conversation memory ───────────────────────────────────────────────────
    history = memory.get_history(request.session_id)
    previous = memory.get_analyses(request.session_id)

    # ── Build initial AgentState ──────────────────────────────────────────────
    initial_state: AgentState = {
        "user_query": request.query,
        "question": request.query,          # backward-compat alias
        "session_id": request.session_id,
        "dataset_ids": request.dataset_ids,
        "dataframes": dataframes,
        "dataset_schema": schemas,          # agents expect singular key
        "rag_context": rag_context,
        "rag_citations": rag_citations,
        "conversation_history": history,
        "previous_analyses": previous,
        "errors": [],
        "metadata": {},
        "completed_tasks": [],              # router node initialisation
    }

    # ── Run agent pipeline ────────────────────────────────────────────────────
    try:
        final_state = await run_agent_pipeline(initial_state)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Agent pipeline failed")
        raise HTTPException(status_code=500, detail=f"Analysis pipeline error: {exc}")

    elapsed = round(time.time() - start_time, 2)

    # ── Evaluation metrics ────────────────────────────────────────────────────
    evaluation_metrics = {
        "datasets_used": len(dataframes),
        "rag_enabled": request.include_rag,
        "rag_citation_count": len(rag_citations),
        "analysis_error_count": len(final_state.get("errors", [])),
        "execution_duration_seconds": elapsed,
    }

    # ── Persist to memory ─────────────────────────────────────────────────────
    memory.add_message(request.session_id, "user", request.query)
    memory.add_message(
        request.session_id, "assistant",
        final_state.get("final_response", "Analysis complete."),
    )
    memory.save_analysis(request.session_id, {
        "query": request.query,
        "insights": final_state.get("insights", [])[:3],
        "datasets": list(dataframes.keys()),
        "evaluation_metrics": evaluation_metrics,
        "rag_citations": final_state.get("rag_citations", rag_citations),
        "report_markdown": final_state.get("report_markdown", ""),
        "execution_plan": final_state.get("execution_plan", []),
        "recommendations": final_state.get("recommendations", []),
    })

    # ── Build response ────────────────────────────────────────────────────────
    # chart_specs is a list of Plotly JSON dicts — frontend reconstructs
    # them with go.Figure(chart) in 02_analyze.py and 03_dashboard.py.
    return AnalysisResponse(
        session_id=request.session_id,
        query=request.query,
        execution_plan=final_state.get("execution_plan", []),
        active_agents=final_state.get("active_agents", []),
        insights=final_state.get("insights", []),
        trends=final_state.get("trends", []),
        recommendations=final_state.get("recommendations", []),
        anomaly_count=len(final_state.get("anomalies", [])),
        anomaly_explanations=final_state.get("anomaly_explanations", []),
        chart_count=len(final_state.get("chart_specs", []) or final_state.get("charts", [])),
        charts=final_state.get("chart_specs", []) or final_state.get("charts", []),
        generated_sql=final_state.get("generated_sql") or final_state.get("sql_query"),
        generated_pandas=final_state.get("generated_pandas") or final_state.get("pandas_code"),
        kpi_summary=final_state.get("kpi_summary", {}),
        executive_summary=(
            final_state.get("metadata", {}).get("executive_summary")
            or final_state.get("executive_summary", "")
        ),
        report_markdown=final_state.get("report_markdown", ""),
        explainability=final_state.get("explainability", {}),
        evaluation_metrics=evaluation_metrics,
        rag_citations=[
            c if isinstance(c, str)
            else f"{c.get('source', 'unknown')} (p{c.get('page_number', '?')}, score={round(float(c.get('relevance_score', 0)), 2)})"
            for c in (final_state.get("rag_citations") or rag_citations)
        ],
        errors=final_state.get("errors", []),
        processing_time_seconds=elapsed,
    )
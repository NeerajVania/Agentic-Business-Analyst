"""
backend/api/routes_evaluation.py
================================
Evaluation endpoints — session-level quality metrics.

  GET /evaluate/{session_id}

Not directly called from Streamlit pages in the current frontend but
available for external tooling, CI quality gates, or a future
"Evaluation" page.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import EvaluationResponse
from memory.redis_memory import get_memory

router = APIRouter()


@router.get("/{session_id}", response_model=EvaluationResponse)
async def evaluate_session(session_id: str) -> EvaluationResponse:
    """Return lightweight evaluation metrics for the latest analysis session."""
    memory = get_memory()
    analyses = memory.get_analyses(session_id)

    if not analyses:
        raise HTTPException(
            status_code=404,
            detail="No analysis history found for this session.",
        )

    latest = analyses[0]
    insights = latest.get("insights", []) or []
    recommendations = latest.get("recommendations", []) or []
    dataset_count = len(latest.get("datasets", []))

    metrics = {
        "analysis_count": len(analyses),
        "dataset_count": dataset_count,
        "insight_count": len(insights),
        "recommendation_count": len(recommendations),
        "has_previous_analysis": True,
    }

    notes = [
        "This endpoint provides an overview of the latest session.",
        "Extend with human quality review and model performance tracking for production use.",
    ]

    evaluation_metrics = {
        "analysis_quality_score": min(1.0, 0.3 + 0.1 * len(insights) + 0.1 * len(recommendations)),
        "retrieval_quality_score": 0.8 if latest.get("rag_citations") else 0.5,
        "agent_success_rate": min(1.0, len(latest.get("execution_plan", [])) / 8),
        "hallucination_risk": "low" if latest.get("rag_citations") else "medium",
        "report_available": bool(latest.get("report_markdown")),
    }

    return EvaluationResponse(
        session_id=session_id,
        metrics=metrics,
        notes=notes,
        last_analysis=latest,
        evaluation_metrics=evaluation_metrics,
    )
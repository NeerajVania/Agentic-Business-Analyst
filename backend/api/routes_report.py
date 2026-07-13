"""
backend/api/routes_report.py
=============================
Report generation and download endpoints.

  POST /generate-report               — generate or retrieve a cached report
  GET  /generate-report/download/{id} — stream report file for download

Frontend consumer
-----------------
  05_reports.py  →  POST /generate-report
    Payload:  { session_id: str, format: "html"|"markdown"|"pdf" }
    Expects:  ReportResponse:
                { session_id, format, content: str|None, file_path: str|None }
    Uses:
      • data["content"]   → st.markdown() preview or components.html() preview
      • st.download_button(data=data["content"])

  05_reports.py  →  GET /generate-report/download/{session_id}?format=pdf
    Streams file as application/octet-stream.
    Linked directly via <a href="..."> in the Direct Download Links card.

Report file naming convention (set by report_agent.py):
  data/reports/report_{session_id}_{timestamp}.{ext}

Fallback generation
-------------------
  When no saved report file is found on disk (e.g. after a server restart),
  the endpoint attempts to rebuild the report from the Redis-persisted
  analysis summary for the session using report_agent helpers.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from loguru import logger

from backend.models.schemas import ReportRequest, ReportResponse

router = APIRouter()


def _find_report_files(
    report_dir: Path, session_id: str, target_suffix: str
) -> list[Path]:
    """Return matching report files sorted newest-first."""
    all_files = sorted(report_dir.glob(f"report_{session_id}_*"), reverse=True)
    return [f for f in all_files if f.suffix == target_suffix]


def _regenerate_from_memory(session_id: str, fmt: str) -> str | None:
    """
    Attempt to rebuild a report from the Redis-persisted analysis summary.

    Returns the report content string on success, or None if insufficient
    data is available in memory.
    """
    try:
        from memory.redis_memory import get_memory
        from agents.report_agent import _render_html, _render_markdown

        memory = get_memory()
        analyses = memory.get_analyses(session_id)
        if not analyses:
            return None

        # Use most recent analysis entry
        latest = analyses[-1]

        ctx = {
            "title": f"Business Intelligence Report — {latest.get('query', 'Analysis')[:60]}",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session_id": session_id,
            "dataset_count": len(latest.get("datasets", [])),
            "executive_summary": latest.get(
                "executive_summary", "Analysis completed — see insights below."
            ),
            "schemas": {},
            "kpi_summary": {},
            "insights": [latest.get("query", "")] if latest.get("query") else [],
            "trends": [],
            "anomaly_explanations": [],
            "recommendations": latest.get("recommendations", []),
            "generated_sql": "",
            "execution_plan": latest.get("execution_plan", []),
        }

        if fmt == "html":
            return _render_html(ctx)
        elif fmt == "markdown":
            return _render_markdown(ctx)
        return None
    except Exception as exc:
        logger.warning("[ReportRoute] Memory-based regeneration failed: {}", exc)
        return None


@router.post("", response_model=ReportResponse)
async def generate_report(request: ReportRequest) -> ReportResponse:
    """
    Return the most-recently generated report for this session.

    Primary path: locate the report file written to ``settings.reports_dir``
    by the report_agent during the /analyze pipeline.

    Fallback path: when no file exists (e.g. server restarted), attempt
    to regenerate a lightweight report from the Redis-persisted analysis
    summary and save it to disk for future requests.

    Returns HTTP 404 only when both paths yield no data.
    """
    from config.settings import get_settings
    settings = get_settings()

    report_dir = settings.reports_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    suffix_map = {"html": ".html", "markdown": ".md", "pdf": ".pdf"}
    target_suffix = suffix_map.get(request.format)

    if not target_suffix:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{request.format}'. Choose html, markdown, or pdf.",
        )

    # ── Primary: find saved report file ──────────────────────────────────────
    matching = _find_report_files(report_dir, request.session_id, target_suffix)

    if matching:
        selected = matching[0]
        logger.info("[ReportRoute] Serving saved report: {}", selected.name)
        if request.format == "pdf":
            return ReportResponse(
                session_id=request.session_id,
                format="pdf",
                file_path=str(selected),
            )
        return ReportResponse(
            session_id=request.session_id,
            format=request.format,
            content=selected.read_text(encoding="utf-8"),
            file_path=str(selected),
        )

    # ── Fallback: regenerate from Redis memory (html/md only) ────────────────
    if request.format != "pdf":
        logger.info(
            "[ReportRoute] No saved file found — attempting memory regeneration for session {}",
            request.session_id,
        )
        content = _regenerate_from_memory(request.session_id, request.format)
        if content:
            # Persist for future requests
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = report_dir / f"report_{request.session_id}_{ts}{target_suffix}"
            out_path.write_text(content, encoding="utf-8")
            logger.info("[ReportRoute] Regenerated report saved: {}", out_path.name)
            return ReportResponse(
                session_id=request.session_id,
                format=request.format,
                content=content,
                file_path=str(out_path),
            )

    raise HTTPException(
        status_code=404,
        detail=(
            f"No {request.format} report found for session '{request.session_id}'. "
            "Run POST /analyze first to generate a report."
        ),
    )


@router.get("/download/{session_id}")
async def download_report(session_id: str, format: str = "pdf"):
    """
    Stream a report file as a binary download.

    Used by the Direct Download Links card in 05_reports.py:
      <a href="{API_BASE}/generate-report/download/{session_id}?format=html">

    Falls back to memory regeneration for html/markdown if no file exists,
    mirroring the behaviour of the POST endpoint.
    """
    from config.settings import get_settings
    settings = get_settings()

    report_dir = settings.reports_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    ext_map = {"html": ".html", "markdown": ".md", "pdf": ".pdf"}
    ext = ext_map.get(format, f".{format}")

    files = sorted(report_dir.glob(f"report_{session_id}_*{ext}"), reverse=True)

    # Fallback regeneration for text formats
    if not files and format in ("html", "markdown"):
        content = _regenerate_from_memory(session_id, format)
        if content:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = report_dir / f"report_{session_id}_{ts}{ext}"
            out_path.write_text(content, encoding="utf-8")
            files = [out_path]

    if not files:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No {format} report found for session '{session_id}'. "
                "Run POST /analyze first."
            ),
        )

    mime_map = {
        ".html": "text/html",
        ".md": "text/markdown",
        ".pdf": "application/pdf",
    }
    mime = mime_map.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(files[0]),
        media_type=mime,
        filename=files[0].name,
    )
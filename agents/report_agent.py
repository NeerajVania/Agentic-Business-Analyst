"""
agents/report_agent.py
=======================
Report Generation Agent.

Assembles the final executive report from all agent outputs.
Produces Markdown and HTML formats (PDF via weasyprint).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Template
from loguru import logger

from agents.state import AgentState
from config.settings import get_settings

settings = get_settings()

# ── Jinja2 HTML template ──────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ title }}</title>
<style>
  body { font-family: 'Segoe UI', sans-serif; max-width: 1100px; margin: 0 auto; padding: 40px; background: #0f172a; color: #e2e8f0; }
  h1 { color: #38bdf8; border-bottom: 2px solid #38bdf8; padding-bottom: 12px; }
  h2 { color: #7dd3fc; margin-top: 36px; }
  h3 { color: #bae6fd; }
  .kpi-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; margin: 20px 0; }
  .kpi-card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }
  .kpi-value { font-size: 1.8rem; font-weight: bold; color: #38bdf8; }
  .kpi-label { color: #94a3b8; font-size: 0.85rem; margin-top: 4px; }
  .insight { background: #1e293b; border-left: 4px solid #38bdf8; padding: 12px 16px; margin: 8px 0; border-radius: 0 6px 6px 0; }
  .recommendation { background: #1e293b; border-left: 4px solid #22c55e; padding: 12px 16px; margin: 8px 0; border-radius: 0 6px 6px 0; }
  .anomaly { background: #1e293b; border-left: 4px solid #ef4444; padding: 12px 16px; margin: 8px 0; border-radius: 0 6px 6px 0; }
  .trend { background: #1e293b; border-left: 4px solid #a78bfa; padding: 12px 16px; margin: 8px 0; border-radius: 0 6px 6px 0; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: bold; }
  .badge-high { background: #ef4444; }
  .badge-medium { background: #f59e0b; color: #000; }
  .badge-low { background: #22c55e; color: #000; }
  code { background: #334155; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; color: #38bdf8; }
  pre { background: #1e293b; padding: 16px; border-radius: 8px; overflow-x: auto; }
  .meta { color: #64748b; font-size: 0.85rem; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; }
  th { background: #1e293b; padding: 10px; text-align: left; color: #7dd3fc; }
  td { padding: 8px 10px; border-bottom: 1px solid #334155; }
  tr:hover { background: #1e293b; }
</style>
</head>
<body>

<h1>📊 {{ title }}</h1>
<p class="meta">Generated: {{ generated_at }} | Session: {{ session_id }} | Datasets: {{ dataset_count }}</p>

<h2>📋 Executive Summary</h2>
<p>{{ executive_summary }}</p>

<h2>🎯 Dataset Overview</h2>
{% for name, schema in schemas.items() %}
<h3>{{ name }}</h3>
<p class="meta">{{ schema.get('rows', 'N/A') }} rows × {{ schema.get('columns_count', 'N/A') }} columns</p>
{% endfor %}

<h2>📈 KPI Analysis</h2>
<div class="kpi-grid">
{% for dataset, kpis in kpi_summary.items() %}
  {% for metric, values in kpis.items() %}
  <div class="kpi-card">
    <div class="kpi-value">{{ "%.2f"|format(values.get('total', 0)) }}</div>
    <div class="kpi-label">{{ metric }} ({{ dataset }})</div>
  </div>
  {% endfor %}
{% endfor %}
</div>

<h2>💡 Business Insights</h2>
{% for insight in insights %}
<div class="insight">{{ insight }}</div>
{% endfor %}

<h2>📉 Trends</h2>
{% for trend in trends %}
<div class="trend">{{ trend }}</div>
{% endfor %}

<h2>⚠️ Anomalies</h2>
{% if anomaly_explanations %}
{% for anomaly in anomaly_explanations %}
<div class="anomaly">{{ anomaly }}</div>
{% endfor %}
{% else %}
<p>No significant anomalies detected.</p>
{% endif %}

<h2>✅ Recommendations</h2>
{% for rec in recommendations %}
<div class="recommendation">{{ rec }}</div>
{% endfor %}

{% if generated_sql %}
<h2>🔍 Generated Query</h2>
<pre><code>{{ generated_sql }}</code></pre>
{% endif %}

<h2>🏁 Conclusion</h2>
<p>This analysis was generated autonomously by the Agentic Data Analyst system using
Mistral AI, multi-agent LangGraph orchestration, and statistical analysis pipelines.
All insights are grounded in the uploaded datasets. For further analysis, please
interact with the system via natural language queries.</p>

<hr>
<p class="meta">Agentic Data Analyst — Powered by Mistral AI + LangGraph + HuggingFace</p>
</body>
</html>
"""

# ── Agent node ────────────────────────────────────────────────────────────────

def report_agent(state: AgentState) -> AgentState:
    """
    LangGraph node: Report Generation Agent.
    Reads all previous agent outputs.
    Writes `report_html`, `report_markdown`, `report_pdf_path`.
    """
    logger.info("[ReportAgent] Assembling final report")

    context = _build_context(state)

    # HTML report
    html = _render_html(context)

    # Markdown report
    markdown = _render_markdown(context)

    # Save to disk
    report_dir = settings.reports_dir
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    session = state.get("session_id", "unknown")

    html_path = report_dir / f"report_{session}_{ts}.html"
    md_path = report_dir / f"report_{session}_{ts}.md"

    html_path.write_text(html, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")

    # PDF (optional — requires weasyprint)
    pdf_path_str = ""
    try:
        from weasyprint import HTML as WP_HTML
        pdf_path = report_dir / f"report_{session}_{ts}.pdf"
        WP_HTML(string=html).write_pdf(str(pdf_path))
        pdf_path_str = str(pdf_path)
        logger.info("[ReportAgent] PDF saved: {}", pdf_path)
    except Exception as exc:
        logger.warning("[ReportAgent] PDF generation skipped: {}", exc)

    logger.info("[ReportAgent] Report saved: {}", html_path)

    return {
        "report_html": html,
        "report_markdown": markdown,
        "report_pdf_path": pdf_path_str,
        "final_response": _build_final_response(state),
    }


# ── Builders ──────────────────────────────────────────────────────────────────

def _build_context(state: AgentState) -> dict[str, Any]:
    """Assemble all state fields into template context."""
    schemas: dict[str, Any] = {}
    for name, schema in (state.get("dataset_schemas") or state.get("dataset_schema") or {}).items():
        schemas[name] = {
            "rows": state.get("analysis_results", {}).get(name, {}).get("shape", {}).get("rows", "N/A"),
            "columns_count": len(schema.get("columns", [])),
        }

    return {
        "title": f"Business Intelligence Report — {state.get('user_query', 'Analysis')[:60]}",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": state.get("session_id", "N/A"),
        "dataset_count": len(state.get("dataframes", {})),
        "executive_summary": state.get("metadata", {}).get(
            "executive_summary", "Comprehensive analysis completed."
        ),
        "schemas": schemas,
        "kpi_summary": state.get("kpi_summary", {}),
        "insights": state.get("insights", []),
        "trends": state.get("trends", []),
        "anomaly_explanations": state.get("anomaly_explanations", []),
        "recommendations": state.get("recommendations", []),
        "generated_sql": state.get("generated_sql", ""),
        "execution_plan": state.get("execution_plan", []),
    }


def _render_html(ctx: dict[str, Any]) -> str:
    tmpl = Template(HTML_TEMPLATE)
    return tmpl.render(**ctx)


def _render_markdown(ctx: dict[str, Any]) -> str:
    lines = [
        f"# {ctx['title']}",
        f"> Generated: {ctx['generated_at']} | Session: {ctx['session_id']}",
        "",
        "## Executive Summary",
        ctx["executive_summary"],
        "",
        "## Business Insights",
    ]
    for i in ctx.get("insights", []):
        lines.append(f"- {i}")

    lines += ["", "## Trends"]
    for t in ctx.get("trends", []):
        lines.append(f"- {t}")

    lines += ["", "## Anomalies"]
    for a in ctx.get("anomaly_explanations", []):
        lines.append(f"- {a}")

    lines += ["", "## Recommendations"]
    for i, r in enumerate(ctx.get("recommendations", []), 1):
        if isinstance(r, dict):
            action   = r.get("action", "")
            priority = r.get("priority", "medium").upper()
            why      = r.get("rationale", "")
            metric   = r.get("metric_referenced", "")
            lines.append(f"\n### {i}. {action}  `[{priority}]`")
            if why:    lines.append(f"**Why:** {why}")
            if metric: lines.append(f"**Metric:** {metric}")
        else:
            parts  = str(r).split(" - ")
            action = parts[0].strip()
            attrs  = {}
            for p in parts[1:]:
                pl = p.lower()
                if pl.startswith("why:"):       attrs["why"]      = p[4:].strip()
                elif pl.startswith("priority:"): attrs["priority"] = p[9:].strip().upper()
                elif pl.startswith("metric:"):   attrs["metric"]   = p[7:].strip()
            priority = attrs.get("priority", "MEDIUM")
            lines.append(f"\n### {i}. {action}  `[{priority}]`")
            if attrs.get("why"):    lines.append(f"**Why:** {attrs['why']}")
            if attrs.get("metric"): lines.append(f"**Metric:** {attrs['metric']}")

    if ctx.get("generated_sql"):
        lines += ["", "## Generated SQL", f"```sql\n{ctx['generated_sql']}\n```"]

    return "\n".join(lines)


def _build_final_response(state: AgentState) -> str:
    """Compose the conversational response shown to the user."""
    summary = state.get("metadata", {}).get("executive_summary", "")
    insights = state.get("insights", [])[:3]
    recs = state.get("recommendations", [])[:2]
    anomaly_count = len(state.get("anomalies", []))

    parts = [summary, ""]
    if insights:
        parts.append("**Key Insights:**")
        parts.extend(f"• {i}" for i in insights)
    if recs:
        parts += ["", "**Top Recommendations:**"]
        parts.extend(f"• {r}" for r in recs)
    if anomaly_count:
        parts += ["", f"⚠️ **{anomaly_count} anomalies detected** — see the Anomalies section of the report."]

    return "\n".join(parts)
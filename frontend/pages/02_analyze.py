"""
frontend/pages/02_analyze.py
=============================
Natural language analysis — POST /analyze
Payload: AnalysisRequest { query, dataset_ids, session_id, include_rag }
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from styles import inject_css, page_header, kpi_row, insight_list, agent_badges, section_title
import api_client as api

st.set_page_config(page_title="Analyze", page_icon="🔍", layout="wide")
inject_css()
from components.sidebar import render_full_sidebar
render_full_sidebar()

page_header("🔍", "Analyze",
            "Ask business questions in plain English — the multi-agent pipeline handles the rest")

if "uploaded_datasets" not in st.session_state:
    st.session_state.uploaded_datasets = {}
if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = None
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())

# ── Guard ──────────────────────────────────────────────────────────────────────
datasets = st.session_state.uploaded_datasets
if not datasets:
    st.markdown(
        """<div class="ui-card" style="text-align:center;padding:56px 40px;">
            <div style="font-size:2.8rem;margin-bottom:14px;opacity:0.5;">📂</div>
            <div style="color:#f0f4ff;font-weight:700;margin-bottom:8px;font-size:1.05rem;">
                No datasets loaded
            </div>
            <div style="color:#9daec8;font-size:0.88rem;max-width:340px;margin:0 auto;line-height:1.6;">
                Go to the <b style="color:#818cf8;">Upload</b> page first
                and upload a CSV, Excel, or JSON dataset.
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.stop()

# ── Query form ─────────────────────────────────────────────────────────────────
st.markdown('<div class="ui-card">', unsafe_allow_html=True)

# Example prompts
st.markdown(
    """<div style="margin:6px 0 12px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
        <span style="font-size:0.72rem;color:#4d6082;font-weight:600;text-transform:uppercase;
                     letter-spacing:0.06em;margin-right:2px;">Try:</span>
    </div>""",
    unsafe_allow_html=True,
)
example_prompts = [
    "Why did sales decrease last quarter?",
    "Which region is underperforming?",
    "Top revenue drivers this month",
    "Detect unusual patterns in the data",
]
ep_cols = st.columns(len(example_prompts))
for col, prompt in zip(ep_cols, example_prompts):
    with col:
        if st.button(prompt, key=f"ep_{prompt[:20]}", width="stretch"):
            st.session_state["query_input"] = prompt
            st.rerun()

with st.form("analyze_form"):
    selected_ids = st.multiselect(
        "Datasets to analyze",
        options=list(datasets.keys()),
        format_func=lambda k: datasets[k]["filename"],
        default=list(datasets.keys()),
        help="Select one or more datasets for cross-dataset analysis",
    )

    query = st.text_area(
        "Business question",
        key="query_input",
        placeholder="e.g. Why did sales decrease last quarter? Which region is underperforming?",
        height=90,
        label_visibility="collapsed",
    )

    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        include_rag = st.checkbox("🧠 RAG knowledge", value=True)
    with col3:
        run_btn = st.form_submit_button(
            "🚀 Run Analysis",
            type="primary",
            width="stretch",
        )

st.markdown('</div>', unsafe_allow_html=True)

# ── Helpers ────────────────────────────────────────────────────────────────────
def _reupload_stale(selected_ids: list) -> list | None:
    """Re-upload datasets when backend was restarted and lost them. Returns new IDs or None."""
    raw_files = st.session_state.get("_raw_files", {})
    files_to_send, id_order = [], []
    for ds_id in selected_ids:
        if ds_id in raw_files:
            name, data, mime = raw_files[ds_id]
            files_to_send.append(("files", (name, data, mime)))
            id_order.append(ds_id)
    if not files_to_send:
        return None
    resp = api.post("/upload/multi", files=files_to_send, timeout=300)
    ok, result = api.safe_json(resp)
    if not ok:
        return None
    new_ids, new_raw = [], {}
    for old_id, ds in zip(id_order, result.get("datasets", [])):
        new_id = ds["dataset_id"]
        st.session_state.uploaded_datasets[new_id] = ds
        st.session_state.uploaded_datasets.pop(old_id, None)
        new_raw[new_id] = raw_files[old_id]
        new_ids.append(new_id)
    st.session_state._raw_files = {
        **{k: v for k, v in raw_files.items() if k not in id_order},
        **new_raw,
    }
    return new_ids


# ── Run pipeline ───────────────────────────────────────────────────────────────
if run_btn:
    if not query or not selected_ids:
        st.warning("Please enter a question and select at least one dataset.")
    else:
        status_box = st.empty()
        status_box.info("Running multi-agent pipeline…")
        with st.spinner("Running multi-agent pipeline…"):
            st.write("🧭 Invoking Planner Agent…")
        active_ids = selected_ids
        payload = {
            "query": query,
            "dataset_ids": active_ids,
            "session_id": st.session_state.session_id,
            "include_rag": include_rag,
        }
        try:
            st.write("⚙️ Executing specialist agents…")
            resp = api.post("/analyze", json=payload, timeout=180)
            ok, data = api.safe_json(resp)

            # Auto-recover from stale IDs (backend restarted) — re-upload and retry once
            if not ok and isinstance(data, str) and "not found" in data.lower():
                status_box.warning("⚠️ Backend was restarted — re-uploading datasets…")
                new_ids = _reupload_stale(active_ids)
                if new_ids:
                    active_ids = new_ids
                    payload["dataset_ids"] = active_ids
                    resp = api.post("/analyze", json=payload, timeout=180)
                    ok, data = api.safe_json(resp)
                else:
                    status_box.error("Datasets lost after backend restart. Please re-upload your files.")
                    st.error("Please go to the **Upload** page and re-upload your files.")
                    st.stop()

            if not ok:
                status_box.error(f"Analysis failed: {data}")
                st.error(f"Analysis failed: {data}")
                st.stop()

            st.session_state.last_analysis = data
            status_box.success(
                f"✅ Analysis complete in {data.get('processing_time_seconds', 0):.1f}s"
            )
        except Exception as e:
            status_box.error("❌ Analysis failed")
            st.error(f"Analysis failed: {e}")
            st.stop()

# ── Results ────────────────────────────────────────────────────────────────────
result = st.session_state.last_analysis
if not result:
    st.markdown(
        """<div style="text-align:center;padding:56px 24px;">
            <div style="font-size:2.5rem;margin-bottom:12px;opacity:0.3;">🔍</div>
            <div style="color:#9daec8;font-size:0.9rem;">
                Enter a question above and click <b style="color:#818cf8;">Run Analysis</b>.
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.stop()

elapsed = result.get("processing_time_seconds", 0)
active_agents = result.get("active_agents", [])
n_insights = len(result.get("insights", []))
n_charts = result.get("chart_count", 0)
n_recs = len(result.get("recommendations", []))
n_anomalies = result.get("anomaly_count", 0)

# ── Summary bar ────────────────────────────────────────────────────────────────
st.markdown(
    f"""<div style="display:flex;align-items:center;justify-content:space-between;
                    background:#111827;border:1px solid rgba(91,108,245,0.15);
                    border-radius:14px;padding:14px 20px;margin-bottom:20px;flex-wrap:wrap;gap:12px;">
        <div style="display:flex;align-items:center;gap:12px;">
            <span class="pill pill-success">✅ Complete</span>
            <span style="color:#4d6082;font-size:0.82rem;">⏱ {elapsed:.1f}s</span>
        </div>
        <div style="display:flex;gap:20px;flex-wrap:wrap;">
            <div style="text-align:center;">
                <div style="font-size:1.1rem;font-weight:700;color:#818cf8;">{n_insights}</div>
                <div style="font-size:0.65rem;color:#4d6082;text-transform:uppercase;
                            letter-spacing:0.06em;">Insights</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:1.1rem;font-weight:700;color:#818cf8;">{n_charts}</div>
                <div style="font-size:0.65rem;color:#4d6082;text-transform:uppercase;
                            letter-spacing:0.06em;">Charts</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:1.1rem;font-weight:700;color:#34d399;">{n_recs}</div>
                <div style="font-size:0.65rem;color:#4d6082;text-transform:uppercase;
                            letter-spacing:0.06em;">Actions</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:1.1rem;font-weight:700;color:#fbbf24;">{n_anomalies}</div>
                <div style="font-size:0.65rem;color:#4d6082;text-transform:uppercase;
                            letter-spacing:0.06em;">Anomalies</div>
            </div>
        </div>
    </div>""",
    unsafe_allow_html=True,
)

if active_agents:
    agent_badges(active_agents)

# ── KPI cards ──────────────────────────────────────────────────────────────────
# kpi_summary shape: { dataset_name: { column: { total, mean, ... } } }
kpis = result.get("kpi_summary", {})
if kpis:
    flat = [
        (f"{col} ({ds})", f"{vals.get('total', 0):,.0f}", f"avg {vals.get('mean', 0):,.1f}")
        for ds, cols in kpis.items()
        for col, vals in (cols.items() if isinstance(cols, dict) else [])
    ]
    if flat:
        kpi_row(flat[:6])

# ── Executive summary ──────────────────────────────────────────────────────────
if result.get("executive_summary"):
    st.markdown(
        f"""<div class="ui-card" style="background:linear-gradient(135deg,
                rgba(91,108,245,0.07) 0%,rgba(124,58,237,0.05) 100%);margin-bottom:20px;">
            <div class="section-title">📋 Executive Summary</div>
            <div style="color:#e2e8f0;font-size:0.92rem;line-height:1.75;">
                {result['executive_summary']}
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

# ── Main tabs ──────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    f"💡 Insights ({n_insights})",
    f"📈 Charts ({n_charts})",
    f"⚠️ Anomalies ({n_anomalies})",
    f"✅ Actions ({n_recs})",
    "🔍 Queries",
])

with tab1:
    insights = result.get("insights", [])
    if insights:
        insight_list(insights, kind="insight")
    else:
        st.markdown('<div style="color:#4d6082;padding:24px 0;text-align:center;">No insights generated.</div>', unsafe_allow_html=True)

    trends = result.get("trends", [])
    if trends:
        st.markdown("<br>", unsafe_allow_html=True)
        section_title("📉 Trends")
        insight_list(trends, kind="insight")

with tab2:
    charts = result.get("charts", [])
    if charts:
        per_row = 2
        for i in range(0, len(charts), per_row):
            cols = st.columns(per_row)
            for j, chart in enumerate(charts[i: i + per_row]):
                with cols[j]:
                    try:
                        if isinstance(chart, str):
                            fig = pio.from_json(chart)
                        else:
                            fig = pio.from_json(json.dumps(chart))
                        fig.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(17,24,39,0.8)",
                            font_color="#9daec8",
                            font_family="Space Grotesk",
                            margin=dict(l=8, r=8, t=40, b=8),
                        )
                        st.plotly_chart(fig, width="stretch")
                    except Exception:
                        st.warning("Could not render chart")
    else:
        st.markdown(
            '<div style="text-align:center;padding:48px;color:#4d6082;">No charts generated for this query.</div>',
            unsafe_allow_html=True,
        )

with tab3:
    exps = result.get("anomaly_explanations", [])
    if exps:
        insight_list(exps, kind="anomaly")
    else:
        st.markdown(
            '<div class="pill pill-success" style="margin:12px 0;">✅ No significant anomalies detected</div>',
            unsafe_allow_html=True,
        )

with tab4:
    recs = result.get("recommendations", [])
    if recs:
        rec_cols = st.columns(2)
        for idx, item in enumerate(recs):
            _action, _priority, _why, _metric = "", "medium", "", ""
            if isinstance(item, dict):
                _action   = item.get("action", str(item))
                _priority = item.get("priority", "medium").lower()
                _why      = item.get("rationale", "")
                _metric   = item.get("metric_referenced", "")
            else:
                parts = str(item).split(" - ")
                _action = parts[0].strip()
                for p in parts[1:]:
                    pl = p.lower()
                    if pl.startswith("why:"):       _why      = p[4:].strip()
                    elif pl.startswith("priority:"): _priority = p[9:].strip().lower()
                    elif pl.startswith("metric:"):   _metric   = p[7:].strip()
            _pc = {"high": "#ef4444", "medium": "#f59e0b", "low": "#22c55e"}.get(_priority, "#818cf8")
            _icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(_priority, "⚪")
            why_html = (
                f"<div style='color:#9daec8;font-size:0.82rem;line-height:1.55;padding:8px 10px;background:#0c1120;border-radius:8px;margin-bottom:8px;'><b style='color:#818cf8;'>Why:</b> {_why}</div>"
                if _why
                else ""
            )
            metric_html = (
                f"<div style='color:#4d6082;font-size:0.76rem;padding-top:4px;'>📐 Metric: <span style='color:#818cf8;'>{_metric}</span></div>"
                if _metric
                else ""
            )
            with rec_cols[idx % 2]:
                st.markdown(
                    f"""<div style="background:#111827;border:1px solid rgba(52,211,153,0.15);
                                 border-radius:12px;padding:16px 18px;margin-bottom:14px;">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:10px;">
                            <div style="color:#f0f4ff;font-size:0.9rem;font-weight:700;line-height:1.45;flex:1;">
                                {_icon} {_action}
                            </div>
                            <span style="background:{_pc}22;color:{_pc};border:1px solid {_pc}55;
                                         border-radius:999px;padding:2px 10px;font-size:0.68rem;
                                         font-weight:700;white-space:nowrap;text-transform:uppercase;">{_priority}</span>
                        </div>
                        {why_html}
                        {metric_html}
                    </div>""",
                    unsafe_allow_html=True,
                )
    else:
        st.markdown('<div style="color:#4d6082;padding:24px 0;text-align:center;">No recommendations generated.</div>', unsafe_allow_html=True)

with tab5:
    col_a, col_b = st.columns(2)
    with col_a:
        if result.get("generated_sql"):
            section_title("SQL Query")
            st.code(result["generated_sql"], language="sql")
    with col_b:
        if result.get("generated_pandas"):
            section_title("Pandas Query")
            st.code(result["generated_pandas"], language="python")
    if not result.get("generated_sql") and not result.get("generated_pandas"):
        st.markdown('<div style="color:#4d6082;padding:24px 0;text-align:center;">No queries were generated for this analysis.</div>', unsafe_allow_html=True)

# ── Extras ─────────────────────────────────────────────────────────────────────
if result.get("execution_plan"):
    with st.expander("🗺️ Execution Plan"):
        for i, step in enumerate(result["execution_plan"], 1):
            st.markdown(
                f'<div class="step-item"><div class="step-num">{i}</div>'
                f'<div class="step-text">{step}</div></div>',
                unsafe_allow_html=True,
            )

if result.get("rag_citations"):
    with st.expander(f"📚 RAG Citations ({len(result['rag_citations'])})"):
        for c in result["rag_citations"]:
            st.markdown(f'<div style="color:#9daec8;font-size:0.84rem;padding:4px 0;">• {c}</div>', unsafe_allow_html=True)

# evaluation_metrics from AnalysisResponse
eval_m = result.get("evaluation_metrics", {})
if eval_m:
    with st.expander("📐 Evaluation Metrics"):
        for k, v in eval_m.items():
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;padding:6px 12px;'
                f'background:#0c1120;border-radius:6px;margin-bottom:4px;">'
                f'<span style="color:#9daec8;font-size:0.83rem;">{k.replace("_"," ").title()}</span>'
                f'<span style="color:#818cf8;font-weight:700;">{v}</span></div>',
                unsafe_allow_html=True,
            )

if result.get("errors"):
    with st.expander(f"⚠️ Pipeline Errors ({len(result['errors'])})"):
        for e in result["errors"]:
            st.error(e)

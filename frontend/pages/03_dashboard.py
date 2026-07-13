"""
frontend/pages/03_dashboard.py
================================
Interactive dashboard — renders analysis results from session state.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import plotly.io as pio
import streamlit as st
from styles import inject_css, page_header, kpi_row, section_title

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
inject_css()
from components.sidebar import render_full_sidebar
render_full_sidebar()

page_header("📊", "Dashboard", "Interactive dashboard built from your latest analysis")

result = st.session_state.get("last_analysis")

if not result:
    st.markdown(
        """<div class="ui-card" style="text-align:center;padding:64px 40px;">
            <div style="font-size:3rem;margin-bottom:16px;opacity:0.4;">📊</div>
            <div style="color:#f0f4ff;font-weight:700;font-size:1.05rem;margin-bottom:8px;">No analysis yet</div>
            <div style="color:#9daec8;font-size:0.88rem;max-width:360px;margin:0 auto;line-height:1.6;">
                Go to the <b style="color:#818cf8;">Analyze</b> page, ask a business question,
                and run the pipeline — your results will appear here automatically.
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.stop()

query          = result.get("query", "")
elapsed        = result.get("processing_time_seconds", 0)
kpis           = result.get("kpi_summary", {})
insights       = result.get("insights", [])
trends         = result.get("trends", [])
recs           = result.get("recommendations", [])
anomaly_exps   = result.get("anomaly_explanations", [])
charts         = result.get("charts", [])
exec_summary   = result.get("executive_summary", "")
active_agents  = result.get("active_agents", [])
sql_query      = result.get("generated_sql", "")
pandas_code    = result.get("generated_pandas", "")

total_anomaly_count = len(anomaly_exps)
display_anomaly_count = min(total_anomaly_count, 8)
anomaly_label = (
    f"Showing top {display_anomaly_count} of {total_anomaly_count} anomalies"
    if total_anomaly_count > display_anomaly_count
    else f"{total_anomaly_count} anomalies"
)

n_insights  = len(insights)
n_charts    = len(charts)
n_recs      = len(recs)
n_anomalies = display_anomaly_count
n_trends    = len(trends)

# ── Header bar ────────────────────────────────────────────────────────────────
st.markdown(
    f"""<div class="ui-card" style="margin-bottom:22px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:18px;">
            <div style="min-width:220px;flex:1;">
                <div style="font-size:0.72rem;color:#9ca3af;text-transform:uppercase;font-weight:700;letter-spacing:0.12em;margin-bottom:8px;">Business question</div>
                <div style="color:#e5e7eb;font-size:1rem;line-height:1.7;">{query or 'No query available'}</div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:12px;flex:1.2;">
                <div style="background:rgba(59,130,246,0.12);border:1px solid rgba(59,130,246,0.18);border-radius:14px;padding:14px;">
                    <div style="font-size:0.72rem;color:#bfdbfe;text-transform:uppercase;font-weight:700;letter-spacing:0.08em;margin-bottom:6px;">Elapsed</div>
                    <div style="font-size:1.05rem;color:#f8fafc;font-weight:700;">{elapsed:.1f}s</div>
                </div>
                <div style="background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.18);border-radius:14px;padding:14px;">
                    <div style="font-size:0.72rem;color:#bbf7d0;text-transform:uppercase;font-weight:700;letter-spacing:0.08em;margin-bottom:6px;">Insights</div>
                    <div style="font-size:1.05rem;color:#f8fafc;font-weight:700;">{n_insights}</div>
                </div>
                <div style="background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.18);border-radius:14px;padding:14px;">
                    <div style="font-size:0.72rem;color:#fef3c7;text-transform:uppercase;font-weight:700;letter-spacing:0.08em;margin-bottom:6px;">Anomalies</div>
                    <div style="font-size:1.05rem;color:#f8fafc;font-weight:700;">{anomaly_label}</div>
                </div>
            </div>
        </div>
    </div>""",
    unsafe_allow_html=True,
)

# ── KPI cards ─────────────────────────────────────────────────────────────────
if kpis:
    flat = [
        (f"{col} ({ds})", f"{vals.get('total', 0):,.0f}", f"avg {vals.get('mean', 0):,.1f}")
        for ds, cols in kpis.items()
        for col, vals in (cols.items() if isinstance(cols, dict) else [])
    ]
    if flat:
        section_title("📐 Key Metrics")
        kpi_row(flat[:6])

# ── Executive summary ─────────────────────────────────────────────────────────
if exec_summary:
    st.markdown(
        f"""<div class="ui-card" style="background:linear-gradient(135deg,
                rgba(91,108,245,0.08) 0%,rgba(124,58,237,0.06) 100%);margin-bottom:20px;">
            <div class="section-title">📋 Executive Summary</div>
            <div style="color:#e2e8f0;font-size:0.92rem;line-height:1.8;">{exec_summary}</div>
        </div>""",
        unsafe_allow_html=True,
    )

# ── Charts ────────────────────────────────────────────────────────────────────
if charts:
    section_title(f"📊 Charts ({n_charts})")
    per_row = 2
    for i in range(0, len(charts), per_row):
        cols = st.columns(per_row)
        for j, chart in enumerate(charts[i: i + per_row]):
            with cols[j]:
                try:
                    fig = pio.from_json(chart) if isinstance(chart, str) else pio.from_json(json.dumps(chart))
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

st.markdown("<br>", unsafe_allow_html=True)

# ── Generated queries ─────────────────────────────────────────────────────────
if sql_query or pandas_code:
    section_title("🧾 Generated Queries")
    cols = st.columns(2)
    with cols[0]:
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:700;color:#93c5fd;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">SQL Query</div>',
            unsafe_allow_html=True,
        )
        if sql_query:
            st.code(sql_query, language="sql")
        else:
            st.markdown('<div class="ui-card">No SQL query was generated for this analysis.</div>', unsafe_allow_html=True)
    with cols[1]:
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:700;color:#c7d2fe;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">Pandas Code</div>',
            unsafe_allow_html=True,
        )
        if pandas_code:
            st.code(pandas_code, language="python")
        else:
            st.markdown('<div class="ui-card">No Pandas code was generated for this analysis.</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

# ── 3-column panel ────────────────────────────────────────────────────────────
col_left, col_mid, col_right = st.columns([1.1, 1, 1])

with col_left:
    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;color:#818cf8;text-transform:uppercase;'
        'letter-spacing:0.08em;margin-bottom:12px;">💡 Key Insights</div>',
        unsafe_allow_html=True,
    )
    if insights:
        for item in insights:
            st.markdown(f'<div class="insight-item" style="margin-bottom:10px;">{item}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="color:#4d6082;font-size:0.85rem;">No insights generated.</div>', unsafe_allow_html=True)

with col_mid:
    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;color:#a78bfa;text-transform:uppercase;'
        'letter-spacing:0.08em;margin-bottom:12px;">📈 Trends</div>',
        unsafe_allow_html=True,
    )
    if trends:
        for item in trends:
            st.markdown(
                f"""<div style="background:#1a2540;border-left:3px solid #a78bfa;
                             border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px;
                             color:#e2e8f0;font-size:0.85rem;line-height:1.55;">{item}</div>""",
                unsafe_allow_html=True,
            )
    else:
        st.markdown('<div style="color:#4d6082;font-size:0.85rem;">No trends detected.</div>', unsafe_allow_html=True)

with col_right:
    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;color:#34d399;text-transform:uppercase;'
        'letter-spacing:0.08em;margin-bottom:12px;">✅ Actions</div>',
        unsafe_allow_html=True,
    )
    if recs:
        for item in recs:
            _action, _priority, _why, _metric = "", "medium", "", ""
            if isinstance(item, dict):
                _action   = item.get("action", "").strip() or str(item)
                _priority = item.get("priority", "medium").lower()
                _why      = item.get("rationale", "")
                _metric   = item.get("metric_referenced", "")
            else:
                text = str(item).strip()
                parts = [p.strip() for p in text.split(" - ") if p.strip()]
                _action = parts[0] if parts else text
                for p in parts[1:]:
                    pl = p.lower()
                    if pl.startswith("why:"):       _why      = p[4:].strip()
                    elif pl.startswith("priority:"): _priority = p[9:].strip().lower()
                    elif pl.startswith("metric:"):   _metric   = p[7:].strip()
            _pc = {"high": "#ef4444", "medium": "#f59e0b", "low": "#22c55e"}.get(_priority, "#818cf8")
            why_html = f"<div style='color:#cbd5e1;font-size:0.82rem;line-height:1.5;margin-top:6px;'>{_why}</div>" if _why else ""
            metric_html = f"<div style='color:#94a3b8;font-size:0.78rem;line-height:1.45;margin-top:4px;'>📐 {_metric}</div>" if _metric else ""
            st.markdown(
                f"""<div class="rec-item" style="background:rgba(14,165,233,0.06);border-left:3px solid #60a5fa;padding:16px 18px;margin-bottom:12px;">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;">
                        <div style="color:#f8fafc;font-size:0.95rem;font-weight:700;line-height:1.4;">{_action}</div>
                        <span style="background:{_pc}22;color:{_pc};border:1px solid {_pc}44;border-radius:999px;
                                     padding:4px 10px;font-size:0.72rem;font-weight:700;
                                     white-space:nowrap;text-transform:uppercase;">{_priority}</span>
                    </div>
                    {why_html}
                    {metric_html}
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.markdown('<div style="color:#4d6082;font-size:0.85rem;">No actions generated.</div>', unsafe_allow_html=True)

# ── Anomalies ─────────────────────────────────────────────────────────────────
if anomaly_exps:
    st.markdown("<br>", unsafe_allow_html=True)
    section_title(f"⚠️ Top {display_anomaly_count} Anomalies")
    if total_anomaly_count > display_anomaly_count:
        st.markdown(
            f'<div style="color:#94a3b8;font-size:0.85rem;margin-top:-10px;margin-bottom:12px;">Showing the most important {display_anomaly_count} anomalies out of {total_anomaly_count} detected.</div>',
            unsafe_allow_html=True,
        )
    for exp in anomaly_exps[:display_anomaly_count]:
        sev   = "HIGH" if "[HIGH]" in exp else "MEDIUM" if "[MEDIUM]" in exp else "LOW"
        color = {"HIGH": "#fb7185", "MEDIUM": "#fbbf24", "LOW": "#34d399"}.get(sev, "#60a5fa")
        st.markdown(
            f"""<div class="anomaly-item" style="background:rgba(239,68,68,0.06);border-left:3px solid {color};padding:14px 16px;margin-bottom:10px;">
                    <div style="font-size:0.88rem;color:#f8fafc;font-weight:600;margin-bottom:6px;">{exp}</div>
                </div>""",
            unsafe_allow_html=True,
        )

# ── Active agents ─────────────────────────────────────────────────────────────
if active_agents:
    st.markdown("<br>", unsafe_allow_html=True)
    badges = "".join(f'<span class="agent-badge">⚡ {a}</span>' for a in active_agents)
    st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:4px;">{badges}</div>', unsafe_allow_html=True)

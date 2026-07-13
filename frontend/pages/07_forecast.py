"""
frontend/pages/07_forecast.py
==============================
Time-series forecasting interface — calls POST /forecast

ForecastRequest:  { dataset_id, date_column, target_column, periods, method, session_id }
ForecastResponse: { session_id, target_column, method, forecast, chart, summary,
                    model_metrics, errors }

Fixes applied vs original:
  - Removed stray 'python' text at top of file (copy-paste artifact)
  - Replaced raw `requests` calls with `api_client` (consistent with all other pages)
  - Added `render_full_sidebar()` (was missing entirely)
  - Errors now handled via `api.safe_json()` with friendly messages
  - Backend 422 validation errors (bad column names) surface cleanly
  - HTTP timeout / connection errors caught and displayed properly
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from styles import inject_css, page_header, section_title, kpi_row
import api_client as api

st.set_page_config(page_title="Forecasting", page_icon="🔮", layout="wide")
inject_css()

from components.sidebar import render_full_sidebar
render_full_sidebar()

# ── Extra forecast-specific CSS ────────────────────────────────────────────────
st.markdown("""
<style>
.method-card {
    background: #111827;
    border: 2px solid rgba(91,108,245,0.12);
    border-radius: 14px;
    padding: 18px 20px;
    transition: all 0.22s ease;
    position: relative;
    overflow: hidden;
}
.method-card.active {
    border-color: #5b6cf5;
    background: rgba(91,108,245,0.08);
    box-shadow: 0 0 24px rgba(91,108,245,0.15);
}
.method-card::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(91,108,245,0.04) 0%, transparent 60%);
    pointer-events: none;
}
.method-title {
    font-size: 1rem;
    font-weight: 700;
    color: #f0f4ff;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.method-badge {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    padding: 2px 8px;
    border-radius: 999px;
    background: rgba(91,108,245,0.15);
    color: #818cf8;
    border: 1px solid rgba(91,108,245,0.25);
}
.method-desc {
    font-size: 0.8rem;
    color: #4d6082;
    line-height: 1.55;
    margin-top: 6px;
}
.method-pros {
    margin-top: 10px;
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
}
.pro-tag {
    font-size: 0.7rem;
    padding: 3px 9px;
    border-radius: 6px;
    background: rgba(14,165,122,0.1);
    color: #34d399;
    border: 1px solid rgba(14,165,122,0.2);
    font-weight: 500;
}
.cfg-box-label {
    font-size: 0.65rem;
    font-weight: 700;
    color: #4d6082;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    margin-bottom: 10px;
}
.result-strip {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    background: #111827;
    border: 1px solid rgba(91,108,245,0.15);
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 18px;
    align-items: center;
}
.rs-item { text-align: center; }
.rs-val {
    font-size: 1.3rem;
    font-weight: 800;
    color: #818cf8;
    font-family: 'Syne', sans-serif;
    display: block;
    line-height: 1;
}
.rs-lbl {
    font-size: 0.65rem;
    font-weight: 600;
    color: #4d6082;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-top: 3px;
}
.rs-divider {
    width: 1px;
    height: 36px;
    background: rgba(91,108,245,0.15);
    margin: 0 4px;
}
.chart-wrap {
    background: #111827;
    border: 1px solid rgba(91,108,245,0.15);
    border-radius: 14px;
    overflow: hidden;
    padding: 4px;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
if "uploaded_datasets" not in st.session_state:
    st.session_state.uploaded_datasets = {}
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "forecast_result" not in st.session_state:
    st.session_state.forecast_result = None
if "forecast_cfg" not in st.session_state:
    st.session_state.forecast_cfg = {}

# ── Page header ────────────────────────────────────────────────────────────────
page_header("🔮", "Time-Series Forecasting",
            "Predict future trends using Prophet & ARIMA with confidence intervals and visual diagnostics")

datasets = st.session_state.uploaded_datasets
if not datasets:
    st.markdown(
        """<div class="ui-card" style="text-align:center;padding:64px 40px;">
            <div style="font-size:3rem;margin-bottom:16px;opacity:0.4;
                        filter:drop-shadow(0 0 20px rgba(91,108,245,0.4));">🔮</div>
            <div style="color:#f0f4ff;font-weight:700;font-size:1.05rem;margin-bottom:10px;">
                No datasets loaded
            </div>
            <div style="color:#9daec8;font-size:0.88rem;max-width:340px;margin:0 auto;line-height:1.6;">
                Go to the <b style="color:#818cf8;">Upload</b> page and upload a dataset
                with a date/time column to get started.
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.stop()

# ════════════════════════════════════════════════════════════════════
# Configuration panel
# ════════════════════════════════════════════════════════════════════
st.markdown('<div class="ui-card">', unsafe_allow_html=True)
section_title("⚙️ Forecast Configuration")

# Row 1: dataset + columns
cfg_a, cfg_b, cfg_c = st.columns(3, gap="large")

with cfg_a:
    st.markdown('<div class="cfg-box-label">📂 Dataset</div>', unsafe_allow_html=True)
    dataset_id = st.selectbox(
        "Dataset",
        options=list(datasets.keys()),
        format_func=lambda x: datasets[x].get("filename", x),
        label_visibility="collapsed",
    )
    meta   = datasets[dataset_id]
    schema = meta.get("schema", {})
    st.markdown(
        f'<div style="color:#4d6082;font-size:0.76rem;margin-top:4px;">'
        f'{meta.get("filename","?")} · {meta.get("rows",0):,} rows</div>',
        unsafe_allow_html=True,
    )

with cfg_b:
    st.markdown('<div class="cfg-box-label">📅 Date Column</div>', unsafe_allow_html=True)
    all_cols  = schema.get("columns", [])
    date_cols = schema.get("date_columns", [])
    if not date_cols:
        date_cols = [
            c for c in all_cols
            if any(k in c.lower() for k in ("date", "time", "month", "year", "day", "week"))
        ]
    if not date_cols:
        st.error("❌ No date columns detected. Forecasting requires a time column.")
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()
    date_column = st.selectbox("Date column", options=date_cols, label_visibility="collapsed")

with cfg_c:
    st.markdown('<div class="cfg-box-label">📊 Target Column</div>', unsafe_allow_html=True)
    num_cols = schema.get("numeric_columns", [])
    if not num_cols:
        num_cols = [c for c in all_cols if c not in date_cols]
    if not num_cols:
        st.error("❌ No numeric columns found.")
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()
    target_column = st.selectbox("Target column", options=num_cols, label_visibility="collapsed")

st.markdown("<br>", unsafe_allow_html=True)

# Row 2: method cards + horizon
m_col, h_col = st.columns([2, 1], gap="large")

with m_col:
    st.markdown('<div class="cfg-box-label">🤖 Forecasting Method</div>', unsafe_allow_html=True)
    method = st.radio(
        "Method",
        options=["prophet", "arima"],
        format_func=lambda x: {"prophet": "📈 Prophet", "arima": "📉 ARIMA"}[x],
        horizontal=True,
        label_visibility="collapsed",
    )
    method_details = {
        "prophet": {
            "desc": "Facebook's open-source library. Handles seasonality, holidays, and missing values automatically.",
            "pros": ["Handles seasonality", "Robust to outliers", "Confidence intervals", "Holiday effects"],
            "best": "Seasonal / trend data",
        },
        "arima": {
            "desc": "Statistical autoregressive model. Lightweight and fast — ideal for stationary time-series.",
            "pros": ["Fast inference", "Stationary data", "Lightweight", "Interpretable"],
            "best": "Stationary data",
        },
    }
    d = method_details[method]
    pros_html = "".join(f'<span class="pro-tag">{p}</span>' for p in d["pros"])
    st.markdown(
        f"""<div class="method-card active" style="margin-top:8px;">
            <div class="method-title">
                {"📈" if method == "prophet" else "📉"} {method.upper()}
                <span class="method-badge">Best for: {d['best']}</span>
            </div>
            <div class="method-desc">{d['desc']}</div>
            <div class="method-pros">{pros_html}</div>
        </div>""",
        unsafe_allow_html=True,
    )

with h_col:
    st.markdown('<div class="cfg-box-label">📅 Forecast Horizon</div>', unsafe_allow_html=True)
    periods = st.slider(
        "Periods",
        min_value=7, max_value=365, value=30, step=7,
        label_visibility="collapsed",
    )
    st.markdown(
        f"""<div style="background:rgba(91,108,245,0.08);border:1px solid rgba(91,108,245,0.2);
                        border-radius:10px;padding:14px;text-align:center;margin-top:10px;">
            <div style="font-size:2rem;font-weight:800;color:#818cf8;
                        font-family:'Syne',sans-serif;line-height:1;">{periods}</div>
            <div style="font-size:0.7rem;color:#4d6082;font-weight:600;
                        text-transform:uppercase;letter-spacing:0.08em;margin-top:4px;">
                periods ahead
            </div>
            <div style="font-size:0.73rem;color:#34d399;margin-top:6px;font-weight:500;">
                ≈ {periods // 30 if periods >= 30 else 0} months {periods % 30} days
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

_, _, run_col = st.columns([1, 1, 1])
with run_col:
    run_btn = st.button(
        "🔮 Generate Forecast",
        type="primary",
        width="stretch",
    )

st.markdown('</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# Run forecast — uses api_client (consistent with all other pages)
# ════════════════════════════════════════════════════════════════════
if run_btn:
    st.session_state.forecast_result = None
    status_box = st.empty()
    status_box.info(f"Running {method.upper()} forecast for {periods} periods…")
    with st.spinner(f"Running {method.upper()} forecast for {periods} periods…"):
        st.write(f"📊 Loading dataset `{meta.get('filename', '')}`…")
        st.write(f"🤖 Fitting {method.upper()} model on `{target_column}`…")
        st.write(f"📅 Projecting {periods} periods from last known date…")

        payload = {
            "dataset_id": dataset_id,
            "date_column": date_column,
            "target_column": target_column,
            "periods": periods,
            "method": method,
            "session_id": st.session_state.session_id,
        }
        try:
            resp = api.post("/forecast", json=payload, timeout=120)
            ok, data = api.safe_json(resp)

            if not ok:
                status_box.error(f"Forecast failed: {data}")
                st.error(f"Forecast error: {data}")
                st.stop()

            st.session_state.forecast_result = data
            st.session_state.forecast_cfg = {
                "method": method,
                "periods": periods,
                "target": target_column,
                "date": date_column,
            }
            status_box.success("✅ Forecast complete!")

        except Exception as e:
            status_box.error("❌ Forecast failed")
            st.error(f"Connection error: {e}")
            st.stop()

# ════════════════════════════════════════════════════════════════════
# Results
# ════════════════════════════════════════════════════════════════════
result = st.session_state.forecast_result
cfg    = st.session_state.forecast_cfg

if not result:
    st.markdown(
        """<div style="text-align:center;padding:56px 24px;">
            <div style="font-size:2.8rem;margin-bottom:12px;opacity:0.3;">🔮</div>
            <div style="color:#9daec8;font-size:0.9rem;">
                Configure the options above and click
                <b style="color:#818cf8;">Generate Forecast</b>.
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.stop()

st.divider()

# ── Result strip ─────────────────────────────────────────────────────
fc_data     = result.get("forecast", [])
n_pts       = len(fc_data)
method_used = cfg.get("method", "?").upper()
target_used = cfg.get("target", "?")
horizon     = cfg.get("periods", "?")

last_val  = fc_data[-1].get("yhat", fc_data[-1].get("value", "—")) if fc_data else "—"
first_val = fc_data[0].get("yhat",  fc_data[0].get("value",  "—")) if fc_data else "—"
try:
    trend_pct = ((float(last_val) - float(first_val)) / abs(float(first_val))) * 100 \
                if float(first_val) != 0 else 0
    trend_str = f"{'▲' if trend_pct >= 0 else '▼'} {abs(trend_pct):.1f}%"
    trend_col = "#34d399" if trend_pct >= 0 else "#f87171"
except Exception:
    trend_str = "—"
    trend_col = "#4d6082"

st.markdown(
    f"""<div class="result-strip">
        <div class="rs-item">
            <span class="rs-val">{method_used}</span>
            <div class="rs-lbl">Method</div>
        </div>
        <div class="rs-divider"></div>
        <div class="rs-item">
            <span class="rs-val">{horizon}</span>
            <div class="rs-lbl">Periods</div>
        </div>
        <div class="rs-divider"></div>
        <div class="rs-item">
            <span class="rs-val">{n_pts}</span>
            <div class="rs-lbl">Data points</div>
        </div>
        <div class="rs-divider"></div>
        <div class="rs-item">
            <span class="rs-val" style="color:{trend_col};">{trend_str}</span>
            <div class="rs-lbl">Trend (period)</div>
        </div>
        <div style="margin-left:auto;">
            <span class="pill pill-success">✅ Forecast ready</span>
        </div>
    </div>""",
    unsafe_allow_html=True,
)

# ── Summary card ──────────────────────────────────────────────────────
if result.get("summary"):
    st.markdown(
        f"""<div class="ui-card" style="background:linear-gradient(135deg,
                rgba(91,108,245,0.07) 0%,rgba(124,58,237,0.05) 100%);margin-bottom:20px;">
            <div class="section-title">📋 Forecast Summary</div>
            <div style="color:#e2e8f0;line-height:1.75;font-size:0.92rem;">{result['summary']}</div>
        </div>""",
        unsafe_allow_html=True,
    )

# ── Main tabs ─────────────────────────────────────────────────────────
tab_chart, tab_table, tab_diag = st.tabs([
    "📈 Forecast Chart",
    f"📋 Forecast Data ({n_pts} rows)",
    "🧪 Model Diagnostics",
])

# ── Tab 1: Chart ──────────────────────────────────────────────────────
with tab_chart:
    if result.get("chart"):
        st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        try:
            fig = go.Figure(result["chart"])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(17,24,39,0.85)",
                font_color="#9daec8",
                font_family="Space Grotesk",
                margin=dict(l=12, r=12, t=44, b=12),
                legend=dict(
                    bgcolor="rgba(11,16,34,0.8)",
                    bordercolor="rgba(91,108,245,0.2)",
                    borderwidth=1,
                    font=dict(color="#9daec8", size=11),
                ),
                xaxis=dict(gridcolor="rgba(91,108,245,0.08)", zerolinecolor="rgba(91,108,245,0.15)"),
                yaxis=dict(gridcolor="rgba(91,108,245,0.08)", zerolinecolor="rgba(91,108,245,0.15)"),
            )
            st.plotly_chart(fig, width="stretch")
        except Exception as e:
            st.warning(f"Could not render forecast chart: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="text-align:center;padding:40px;color:#4d6082;">No chart data returned from backend.</div>',
            unsafe_allow_html=True,
        )

# ── Tab 2: Data table ─────────────────────────────────────────────────
with tab_table:
    if fc_data:
        df_fc = pd.DataFrame(fc_data)

        hl_col, _, dl_col = st.columns([2, 2, 1])
        with hl_col:
            show_ci = st.checkbox("Show confidence intervals", value=True)
        with dl_col:
            csv_data = df_fc.to_csv(index=False)
            st.download_button(
                "⬇️ Download CSV",
                data=csv_data,
                file_name=f"forecast_{target_used}_{method_used.lower()}.csv",
                mime="text/csv",
                width="stretch",
            )

        display_df = df_fc.copy()
        if not show_ci:
            ci_cols = [
                c for c in display_df.columns
                if any(k in c.lower() for k in ("lower", "upper", "yhat_lower", "yhat_upper"))
            ]
            display_df = display_df.drop(columns=ci_cols, errors="ignore")

        st.dataframe(display_df, width="stretch", height=380)
    else:
        st.info("No forecast table data available.")

# ── Tab 3: Diagnostics ────────────────────────────────────────────────
with tab_diag:
    diag_left, diag_right = st.columns(2, gap="large")

    with diag_left:
        st.markdown(
            f"""<div class="ui-card">
                <div class="section-title">📌 Model Config</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                    <div style="background:#0c1120;border-radius:8px;padding:12px;">
                        <div style="font-size:0.65rem;color:#4d6082;text-transform:uppercase;
                                    letter-spacing:.07em;">Method</div>
                        <div style="color:#818cf8;font-weight:700;margin-top:3px;">{method_used}</div>
                    </div>
                    <div style="background:#0c1120;border-radius:8px;padding:12px;">
                        <div style="font-size:0.65rem;color:#4d6082;text-transform:uppercase;
                                    letter-spacing:.07em;">Target</div>
                        <div style="color:#f0f4ff;font-weight:600;margin-top:3px;
                                    word-break:break-all;font-size:0.85rem;">{target_used}</div>
                    </div>
                    <div style="background:#0c1120;border-radius:8px;padding:12px;">
                        <div style="font-size:0.65rem;color:#4d6082;text-transform:uppercase;
                                    letter-spacing:.07em;">Date col</div>
                        <div style="color:#f0f4ff;font-weight:600;margin-top:3px;
                                    font-size:0.85rem;">{cfg.get('date', '?')}</div>
                    </div>
                    <div style="background:#0c1120;border-radius:8px;padding:12px;">
                        <div style="font-size:0.65rem;color:#4d6082;text-transform:uppercase;
                                    letter-spacing:.07em;">Horizon</div>
                        <div style="color:#f0f4ff;font-weight:600;margin-top:3px;">
                            {horizon} periods</div>
                    </div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # model_metrics from ForecastResponse (optional)
        if result.get("model_metrics"):
            st.markdown(
                '<div class="section-title" style="margin-top:16px;">📐 Model Metrics</div>',
                unsafe_allow_html=True,
            )
            for k, v in result["model_metrics"].items():
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:9px 14px;background:#0c1120;border-radius:8px;margin-bottom:6px;">'
                    f'<span style="color:#9daec8;font-size:0.83rem;">{k}</span>'
                    f'<span style="color:#818cf8;font-weight:700;'
                    f'font-family:\'JetBrains Mono\',monospace;">{v}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    with diag_right:
        st.markdown(
            """<div class="ui-card">
                <div class="section-title">📚 Method Guide</div>
                <div style="background:#0c1120;border-radius:10px;padding:16px;margin-bottom:10px;">
                    <div style="color:#818cf8;font-weight:700;margin-bottom:8px;">📈 Prophet</div>
                    <div style="color:#4d6082;font-size:0.8rem;line-height:1.6;">
                        Decomposes the series into trend + seasonality + holidays.
                        Great for business data with weekly/monthly cycles and missing values.
                    </div>
                    <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px;">
                        <span class="pro-tag">Seasonal</span>
                        <span class="pro-tag">Holidays</span>
                        <span class="pro-tag">Missing data OK</span>
                    </div>
                </div>
                <div style="background:#0c1120;border-radius:10px;padding:16px;">
                    <div style="color:#818cf8;font-weight:700;margin-bottom:8px;">📉 ARIMA</div>
                    <div style="color:#4d6082;font-size:0.8rem;line-height:1.6;">
                        Autoregressive Integrated Moving Average. Best when the series
                        is stationary (constant mean/variance). Faster and lighter than Prophet.
                    </div>
                    <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px;">
                        <span class="pro-tag">Fast</span>
                        <span class="pro-tag">Stationary data</span>
                        <span class="pro-tag">Lightweight</span>
                    </div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    # errors list from ForecastResponse
    if result.get("errors"):
        with st.expander(f"⚠️ Pipeline Warnings ({len(result['errors'])})"):
            for e in result["errors"]:
                st.warning(e)

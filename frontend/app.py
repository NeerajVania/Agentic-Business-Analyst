"""
frontend/app.py
================
Main Streamlit application — landing page and navigation shell.
Integrated with backend health check and auth-aware session init.
"""

import uuid
import requests
import streamlit as st
from styles import inject_css, API_BASE
from components.sidebar import render_navigation_menu

st.set_page_config(
    page_title="Agentic Data Analyst",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# ── Session state ──────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "uploaded_datasets" not in st.session_state:
    st.session_state.uploaded_datasets = {}
if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None

# ── Backend health check ───────────────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def check_backend_health():
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        return r.ok, r.json() if r.ok else {}
    except Exception:
        return False, {}

backend_ok, health_data = check_backend_health()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """<div style="padding:20px 4px 20px;">
            <div style="font-family:'Syne',sans-serif;font-size:1.35rem;font-weight:800;
                        background:linear-gradient(135deg,#818cf8,#5b6cf5);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                        line-height:1.2;">🧠 Agentic<br>Analyst</div>
            <div style="font-size:0.68rem;color:#4d6082;margin-top:4px;font-weight:600;
                        text-transform:uppercase;letter-spacing:0.1em;">Autonomous BI System</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Backend status badge
    status_color = "#34d399" if backend_ok else "#f87171"
    status_label = f"API {health_data.get('env', 'online')}" if backend_ok else "API offline"
    st.markdown(
        f"""<div style="display:flex;align-items:center;gap:7px;padding:6px 10px;
                        background:rgba(0,0,0,0.2);border-radius:8px;margin-bottom:12px;">
            <div style="width:7px;height:7px;border-radius:50%;background:{status_color};
                        box-shadow:0 0 6px {status_color};flex-shrink:0;"></div>
            <span style="font-size:0.72rem;color:{status_color};font-weight:600;">{status_label}</span>
        </div>""",
        unsafe_allow_html=True,
    )

    sid = st.session_state.session_id
    n_ds = len(st.session_state.uploaded_datasets)
    has_analysis = st.session_state.last_analysis is not None

    st.markdown(
        f"""<div style="background:#0c1120;border:1px solid rgba(91,108,245,0.15);
                        border-radius:12px;padding:12px 14px;margin-bottom:16px;">
            <div style="font-size:0.65rem;color:#4d6082;text-transform:uppercase;
                        letter-spacing:0.08em;font-weight:700;">Session</div>
            <div style="font-size:0.8rem;color:#818cf8;font-family:'JetBrains Mono',monospace;
                        margin-top:3px;">{sid[:16]}…</div>
            <div style="display:flex;gap:16px;margin-top:10px;padding-top:10px;
                        border-top:1px solid rgba(91,108,245,0.1);">
                <div>
                    <span style="font-size:1.1rem;font-weight:700;color:#818cf8;">{n_ds}</span>
                    <span style="font-size:0.65rem;color:#4d6082;margin-left:4px;">Datasets</span>
                </div>
                <div>
                    <span style="font-size:1.1rem;font-weight:700;
                                 color:{'#34d399' if has_analysis else '#4d6082'};">
                        {'✓' if has_analysis else '—'}
                    </span>
                    <span style="font-size:0.65rem;color:#4d6082;margin-left:4px;">Analysis</span>
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.divider()
    render_navigation_menu()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑 New Session", width="stretch"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ── Backend offline warning ────────────────────────────────────────────────────
if not backend_ok:
    st.warning(
        f"⚠️ **Backend unreachable** — make sure the FastAPI server is running at `{API_BASE}`.  "
        "Run: `uvicorn backend.main:app --reload`",
        icon="🔌",
    )

# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown(
    """<div style="text-align:center;padding:60px 24px 40px;position:relative;">
        <div style="position:absolute;top:0;left:50%;transform:translateX(-50%);
                    width:600px;height:200px;
                    background:radial-gradient(ellipse,rgba(91,108,245,0.12) 0%,transparent 70%);
                    pointer-events:none;"></div>
        <div style="font-size:3.5rem;margin-bottom:16px;filter:drop-shadow(0 0 30px rgba(91,108,245,0.4));">🧠</div>
        <h1 style="font-family:'Syne',sans-serif;font-size:3rem;font-weight:800;margin:0;
                   letter-spacing:-0.03em;
                   background:linear-gradient(135deg,#f0f4ff 0%,#818cf8 50%,#5b6cf5 100%);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            Agentic Data Analyst
        </h1>
        <p style="color:#9daec8;font-size:1rem;margin:14px 0 0;max-width:480px;
                  display:inline-block;line-height:1.6;">
            Autonomous Business Intelligence powered by
            <span style="color:#818cf8;font-weight:600;">Mistral AI</span> +
            <span style="color:#818cf8;font-weight:600;">LangGraph</span>
        </p>
    </div>""",
    unsafe_allow_html=True,
)

# ── Quick Navigation ───────────────────────────────────────────────────────────
nav_cols = st.columns(7)
nav_items = [
    ("📤", "Upload", "01_upload"),
    ("🔍", "Analyze", "02_analyze"),
    ("📊", "Dashboard", "03_dashboard"),
    ("📄", "RAG", "04_rag"),
    ("📑", "Reports", "05_reports"),
    ("💬", "Chat", "06_chat"),
    ("🔮", "Forecast", "07_forecast"),
]

for col, (icon, label, page_name) in zip(nav_cols, nav_items):
    with col:
        if st.button(f"{icon}\n{label}", width="stretch", key=f"top_nav_{page_name}"):
            st.switch_page(f"pages/{page_name}.py")

# ── Stat bar ──────────────────────────────────────────────────────────────────
st.markdown(
    """<div class="stat-bar" style="margin:32px auto;">
        <div class="stat-item">
            <span class="stat-value">8</span>
            <div class="stat-label">AI Agents</div>
        </div>
        <div class="stat-item">
            <span class="stat-value">Mistral</span>
            <div class="stat-label">LLM Core</div>
        </div>
        <div class="stat-item">
            <span class="stat-value">ChromaDB</span>
            <div class="stat-label">Vector DB</div>
        </div>
        <div class="stat-item">
            <span class="stat-value">LangGraph</span>
            <div class="stat-label">Framework</div>
        </div>
        <div class="stat-item">
            <span class="stat-value">Prophet</span>
            <div class="stat-label">Forecasting</div>
        </div>
    </div>""",
    unsafe_allow_html=True,
)

# ── Feature cards ──────────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-size:0.72rem;font-weight:700;color:#4d6082;text-transform:uppercase;'
    'letter-spacing:0.1em;margin:8px 0 20px;text-align:center;">Capabilities</div>',
    unsafe_allow_html=True,
)

features = [
    ("📤", "Upload Datasets", "CSV, Excel & JSON with auto schema detection and join suggestions", "01_upload", "#5b6cf5"),
    ("🤖", "Multi-Agent Analysis", "8 specialist agents orchestrated via LangGraph — answer any business question", "02_analyze", "#7c3aed"),
    ("📊", "Auto Dashboard", "Interactive Plotly charts and KPI cards generated automatically", "03_dashboard", "#0891b2"),
    ("📚", "RAG Knowledge", "Retrieval-Augmented Generation from your company documents", "04_rag", "#059669"),
    ("📑", "Executive Reports", "Professional HTML, Markdown and PDF reports with one click", "05_reports", "#d97706"),
    ("🔮", "Time-Series Forecast", "Prophet & ARIMA forecasts with confidence intervals", "07_forecast", "#db2777"),
]

cols = st.columns(3)
for i, (icon, title, desc, page_name, color) in enumerate(features):
    with cols[i % 3]:
        clicked = st.button(
            f"{icon} {title}",
            width="stretch",
            key=f"nav_card_{page_name}",
            help=desc,
        )
        st.markdown(
            f'<div style="color:#9daec8;font-size:0.78rem;margin:-8px 0 12px 4px;'
            f'line-height:1.5;padding:0 4px;">{desc}</div>',
            unsafe_allow_html=True,
        )
        if clicked:
            st.switch_page(f"pages/{page_name}.py")

st.divider()

# ── Quick start guide ─────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-size:0.72rem;font-weight:700;color:#4d6082;text-transform:uppercase;'
    'letter-spacing:0.1em;margin-bottom:20px;text-align:center;">Quick Start</div>',
    unsafe_allow_html=True,
)

steps = [
    ("1", "📤 Upload", "Drop your CSV, Excel, or JSON files — schema detected automatically"),
    ("2", "🔍 Analyze", "Ask any business question in plain English"),
    ("3", "📊 Explore", "View auto-generated charts and insights on the Dashboard"),
    ("4", "📑 Report", "Download executive reports in PDF, HTML or Markdown"),
]

c1, c2, c3, c4 = st.columns(4)
for col, (num, title, desc) in zip([c1, c2, c3, c4], steps):
    with col:
        st.markdown(
            f"""<div class="ui-card" style="min-height:140px;padding:20px;">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                    <div style="width:28px;height:28px;border-radius:50%;flex-shrink:0;
                                background:linear-gradient(135deg,#5b6cf5,#7c3aed);
                                color:white;font-family:'JetBrains Mono',monospace;
                                font-size:0.72rem;font-weight:700;
                                display:flex;align-items:center;justify-content:center;
                                box-shadow:0 2px 8px rgba(91,108,245,0.35);">{num}</div>
                    <div style="font-weight:700;color:#f0f4ff;font-size:0.88rem;">{title}</div>
                </div>
                <div style="color:#9daec8;font-size:0.81rem;line-height:1.55;">{desc}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown(
    """<div style="text-align:center;padding:24px 0 12px;color:#4d6082;font-size:0.8rem;">
        ← Use the sidebar to navigate between pages
    </div>""",
    unsafe_allow_html=True,
)

"""
frontend/styles.py
==================
Shared CSS theme and utility helpers for all pages.
Enhanced with improved typography, animations, and visual depth.
"""

import os
import streamlit as st

# Internal URL used by the Streamlit server for server-side API calls.
# In Docker: http://backend:8000 (internal Docker network hostname).
API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")

# Public URL used for browser-side links (e.g., <a href=...>).
# When running in Docker the Streamlit server uses http://backend:8000
# internally, but the user's browser must use http://localhost:8000.
# STREAMLIT_PUBLIC_API_BASE can be set explicitly in docker-compose.yml;
# otherwise we fall back to swapping the internal hostname for localhost.
_public_override = os.environ.get("STREAMLIT_PUBLIC_API_BASE", "")
if _public_override:
    PUBLIC_API_BASE = _public_override
else:
    # Replace common internal Docker hostnames with localhost
    PUBLIC_API_BASE = API_BASE.replace("//backend:", "//localhost:")

THEME_CSS = """
<style>
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Syne:wght@700;800&display=swap');

/* ── Root variables ── */
:root {
    --bg-primary:     #050810;
    --bg-secondary:   #0c1120;
    --bg-card:        #111827;
    --bg-card-hover:  #162033;
    --bg-elevated:    #1a2540;
    --accent:         #5b6cf5;
    --accent-2:       #7c3aed;
    --accent-light:   #818cf8;
    --accent-subtle:  rgba(91,108,245,0.12);
    --accent-glow:    rgba(91,108,245,0.3);
    --success:        #0ea57a;
    --success-light:  #34d399;
    --warning:        #d97706;
    --warning-light:  #fbbf24;
    --danger:         #dc2626;
    --danger-light:   #f87171;
    --teal:           #0891b2;
    --pink:           #db2777;
    --text-primary:   #f0f4ff;
    --text-secondary: #9daec8;
    --text-muted:     #4d6082;
    --border:         rgba(91,108,245,0.12);
    --border-hover:   rgba(91,108,245,0.35);
    --border-strong:  rgba(91,108,245,0.5);
    --radius-sm:      8px;
    --radius:         12px;
    --radius-lg:      18px;
    --radius-xl:      24px;
    --shadow-sm:      0 2px 12px rgba(0,0,0,0.3);
    --shadow:         0 6px 32px rgba(0,0,0,0.5);
    --shadow-accent:  0 8px 32px rgba(91,108,245,0.2);
    --shadow-glow:    0 0 60px rgba(91,108,245,0.12);
    --font-body:      'Space Grotesk', sans-serif;
    --font-mono:      'JetBrains Mono', monospace;
    --font-display:   'Syne', sans-serif;
}

/* ── Base ── */
html, body, [class*="css"] {
    font-family: var(--font-body) !important;
    -webkit-font-smoothing: antialiased;
}

.stApp {
    background: var(--bg-primary) !important;
    background-image:
        radial-gradient(ellipse 80% 50% at 20% -10%, rgba(91,108,245,0.07) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 80% 100%, rgba(124,58,237,0.05) 0%, transparent 50%) !important;
    min-height: 100vh;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer { visibility: hidden; }
.stDeployButton { display: none; }
header[data-testid="stHeader"] { background: transparent !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #080c18 0%, #0c1120 100%) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0 !important;
}

/* ── Cards ── */
.ui-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 24px;
    margin-bottom: 16px;
    transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.2s ease;
    box-shadow: var(--shadow-sm);
    position: relative;
    overflow: hidden;
}
.ui-card::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: linear-gradient(135deg, rgba(91,108,245,0.03) 0%, transparent 60%);
    pointer-events: none;
}
.ui-card:hover {
    border-color: var(--border-hover);
    box-shadow: var(--shadow-accent);
    transform: translateY(-2px);
}

/* ── Glass card variant ── */
.glass-card {
    background: rgba(17,24,39,0.7);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(91,108,245,0.15);
    border-radius: var(--radius-lg);
    padding: 24px;
}

/* ── KPI cards ── */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px;
    margin: 16px 0;
}
.kpi-card {
    background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elevated) 100%);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 16px;
    text-align: center;
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
}
.kpi-card::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent), var(--accent-2));
    opacity: 0;
    transition: opacity 0.25s ease;
}
.kpi-card:hover { border-color: var(--border-hover); transform: translateY(-3px); box-shadow: var(--shadow-accent); }
.kpi-card:hover::after { opacity: 1; }
.kpi-value {
    font-family: var(--font-display);
    font-size: 1.9rem;
    font-weight: 700;
    color: var(--accent-light);
    display: block;
    line-height: 1.1;
    letter-spacing: -0.02em;
}
.kpi-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 6px;
}
.kpi-delta {
    font-size: 0.78rem;
    font-weight: 500;
    color: var(--success-light);
    margin-top: 5px;
}

/* ── Page header ── */
.page-header {
    background: linear-gradient(135deg, var(--bg-card) 0%, rgba(91,108,245,0.06) 100%);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: 32px 36px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
}
.page-header::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 280px; height: 280px;
    background: radial-gradient(circle, rgba(91,108,245,0.15) 0%, transparent 65%);
    pointer-events: none;
}
.page-header::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent-glow), transparent);
}
.page-header h1 {
    font-family: var(--font-display) !important;
    font-size: 2rem !important;
    font-weight: 800 !important;
    color: var(--text-primary) !important;
    margin: 0 !important;
    letter-spacing: -0.02em !important;
}
.page-header p {
    color: var(--text-secondary) !important;
    margin: 8px 0 0 !important;
    font-size: 0.92rem !important;
    line-height: 1.5 !important;
}

/* ── Section title ── */
.section-title {
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-title::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
    margin-left: 4px;
}

/* ── Status pills ── */
.pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 14px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.01em;
}
.pill-success { background: rgba(10,165,122,0.12); color: #34d399; border: 1px solid rgba(10,165,122,0.25); }
.pill-warning { background: rgba(217,119,6,0.12);  color: #fbbf24; border: 1px solid rgba(217,119,6,0.25); }
.pill-error   { background: rgba(220,38,38,0.12);  color: #f87171; border: 1px solid rgba(220,38,38,0.25); }
.pill-info    { background: rgba(91,108,245,0.12); color: var(--accent-light); border: 1px solid rgba(91,108,245,0.25); }

/* ── Tag / chip ── */
.tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 600;
    background: rgba(91,108,245,0.1);
    color: var(--accent-light);
    border: 1px solid rgba(91,108,245,0.2);
    margin: 2px;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}

/* ── Insight items ── */
.insight-item {
    background: rgba(91,108,245,0.05);
    border-left: 3px solid var(--accent);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    padding: 14px 18px;
    margin-bottom: 10px;
    color: var(--text-primary);
    font-size: 0.9rem;
    line-height: 1.6;
    transition: background 0.2s ease;
}
.insight-item:hover { background: rgba(91,108,245,0.09); }
.rec-item {
    background: rgba(10,165,122,0.05);
    border-left: 3px solid var(--success);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    padding: 14px 18px;
    margin-bottom: 10px;
    color: var(--text-primary);
    font-size: 0.9rem;
    line-height: 1.6;
}
.anomaly-item {
    background: rgba(217,119,6,0.05);
    border-left: 3px solid var(--warning);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    padding: 14px 18px;
    margin-bottom: 10px;
    color: var(--text-primary);
    font-size: 0.9rem;
    line-height: 1.6;
}

/* ── Step list ── */
.step-item {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding: 12px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.step-item:last-child { border-bottom: none; }
.step-num {
    width: 28px; height: 28px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    color: white;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(91,108,245,0.35);
}
.step-text { color: var(--text-secondary); font-size: 0.87rem; padding-top: 5px; line-height: 1.5; }

/* ── Agent badges ── */
.agent-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 14px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    background: linear-gradient(135deg, rgba(91,108,245,0.15), rgba(124,58,237,0.15));
    color: var(--accent-light);
    border: 1px solid rgba(91,108,245,0.25);
    margin: 3px;
    letter-spacing: 0.02em;
}

/* ── Dataset card ── */
.dataset-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px 18px;
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 10px;
    transition: all 0.2s ease;
}
.dataset-card:hover { border-color: var(--border-hover); background: var(--bg-card-hover); }
.dataset-icon { font-size: 1.5rem; }
.dataset-name { font-weight: 600; color: var(--text-primary); font-size: 0.9rem; }
.dataset-meta { font-size: 0.75rem; color: var(--text-muted); margin-top: 3px; }

/* ── Upload zone ── */
.upload-zone {
    border: 2px dashed rgba(91,108,245,0.3);
    border-radius: var(--radius-lg);
    padding: 44px 24px;
    text-align: center;
    background: rgba(91,108,245,0.03);
    transition: all 0.25s ease;
    cursor: pointer;
}
.upload-zone:hover {
    border-color: var(--accent);
    background: rgba(91,108,245,0.07);
    box-shadow: inset 0 0 40px rgba(91,108,245,0.05);
}

/* ── Streamlit buttons ── */
.stButton > button {
    border-radius: var(--radius-sm) !important;
    font-family: var(--font-body) !important;
    font-weight: 600 !important;
    font-size: 0.86rem !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.01em !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%) !important;
    border: none !important;
    box-shadow: 0 4px 16px rgba(91,108,245,0.3) !important;
    color: white !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(91,108,245,0.45) !important;
}
.stButton > button[kind="secondary"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-secondary) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: var(--border-hover) !important;
    color: var(--text-primary) !important;
    transform: translateY(-1px) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--bg-card) !important;
    border-radius: var(--radius) !important;
    padding: 5px !important;
    gap: 3px !important;
    border: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: var(--radius-sm) !important;
    color: var(--text-muted) !important;
    font-family: var(--font-body) !important;
    font-size: 0.83rem !important;
    font-weight: 600 !important;
    padding: 8px 18px !important;
    transition: all 0.2s ease !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, var(--accent), var(--accent-2)) !important;
    color: white !important;
    box-shadow: 0 2px 10px rgba(91,108,245,0.3) !important;
}

/* ── Inputs ── */
.stTextInput > div > div,
.stTextArea > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.stTextInput > div > div:focus-within,
.stTextArea > div > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(91,108,245,0.12) !important;
}
.stSelectbox > div > div,
.stMultiSelect > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    font-family: var(--font-body) !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 18px !important;
}
[data-testid="stMetric"] label {
    color: var(--text-muted) !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-family: var(--font-display) !important;
    font-weight: 700 !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text-secondary) !important;
    font-family: var(--font-body) !important;
    font-weight: 600 !important;
    transition: border-color 0.2s ease !important;
}
.streamlit-expanderHeader:hover {
    border-color: var(--border-hover) !important;
    color: var(--text-primary) !important;
}

/* ── Code blocks ── */
.stCode, code, pre {
    font-family: var(--font-mono) !important;
}
[data-testid="stCode"] {
    border-radius: var(--radius) !important;
}

/* ── Alert boxes ── */
.stAlert { border-radius: var(--radius) !important; }

/* ── Divider ── */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, var(--border), transparent) !important;
    margin: 28px 0 !important;
}

/* ── Chat bubbles ── */
.chat-user {
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    color: white;
    border-radius: 18px 18px 4px 18px;
    padding: 13px 18px;
    margin: 10px 0 10px 64px;
    font-size: 0.9rem;
    line-height: 1.6;
    box-shadow: 0 4px 16px rgba(91,108,245,0.3);
}
.chat-ai {
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-primary);
    border-radius: 4px 18px 18px 18px;
    padding: 13px 18px;
    margin: 10px 64px 10px 0;
    font-size: 0.9rem;
    line-height: 1.6;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(91,108,245,0.25); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(91,108,245,0.45); }

/* ── Status indicator ── */
.status-dot {
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--success-light);
    box-shadow: 0 0 6px var(--success-light);
    animation: pulse-dot 2s infinite;
}
@keyframes pulse-dot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.6; transform: scale(0.85); }
}

/* ── Progress bar ── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--accent), var(--accent-2)) !important;
    border-radius: 999px !important;
}

/* ── Stat bar ── */
.stat-bar {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 0;
    margin: 32px auto;
    max-width: 700px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
}
.stat-item {
    flex: 1;
    text-align: center;
    padding: 20px 16px;
    border-right: 1px solid var(--border);
    transition: background 0.2s ease;
}
.stat-item:last-child { border-right: none; }
.stat-item:hover { background: var(--bg-elevated); }
.stat-value {
    font-family: var(--font-display);
    font-size: 1.4rem;
    font-weight: 800;
    color: var(--accent-light);
    display: block;
    letter-spacing: -0.02em;
}
.stat-label {
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 3px;
}

/* ── Spinner override ── */
[data-testid="stSpinner"] {
    color: var(--accent-light) !important;
}

/* ── Multiselect tags ── */
[data-baseweb="tag"] {
    background: rgba(91,108,245,0.18) !important;
    border: 1px solid rgba(91,108,245,0.3) !important;
    color: var(--accent-light) !important;
    border-radius: 6px !important;
}

/* ── Number input ── */
.stNumberInput input {
    background: var(--bg-card) !important;
    border-color: var(--border) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
}

/* ── Toggle ── */
.stToggle > label > div {
    background: var(--bg-elevated) !important;
}
</style>
"""


def inject_css():
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str = ""):
    st.markdown(
        f"""<div class="page-header">
            <h1>{icon} {title}</h1>
            {"<p>" + subtitle + "</p>" if subtitle else ""}
        </div>""",
        unsafe_allow_html=True,
    )


def kpi_row(items: list):
    """items = [(label, value, delta), ...]"""
    cols_html = "".join(
        f"""<div class="kpi-card">
            <span class="kpi-value">{val}</span>
            <div class="kpi-label">{label}</div>
            {"<div class='kpi-delta'>▲ " + delta + "</div>" if delta else ""}
        </div>"""
        for label, val, delta in items
    )
    st.markdown(f'<div class="kpi-grid">{cols_html}</div>', unsafe_allow_html=True)


def insight_list(items: list, kind: str = "insight"):
    cls = {"insight": "insight-item", "rec": "rec-item", "anomaly": "anomaly-item"}.get(kind, "insight-item")
    html = "".join(f'<div class="{cls}">{item}</div>' for item in items)
    st.markdown(html, unsafe_allow_html=True)


def agent_badges(agents: list):
    badges = "".join(f'<span class="agent-badge">⚡ {a}</span>' for a in agents)
    st.markdown(f'<div style="margin:10px 0;display:flex;flex-wrap:wrap;gap:2px;">{badges}</div>', unsafe_allow_html=True)


def section_title(label: str):
    st.markdown(f'<div class="section-title">{label}</div>', unsafe_allow_html=True)


def dataset_card(filename: str, rows: int, cols: int, ds_id: str):
    ext = filename.rsplit(".", 1)[-1].upper() if "." in filename else "FILE"
    icon = {"CSV": "📊", "XLSX": "📗", "XLS": "📗", "JSON": "📋"}.get(ext, "📁")
    st.markdown(
        f"""<div class="dataset-card">
            <div class="dataset-icon">{icon}</div>
            <div style="flex:1;min-width:0;">
                <div class="dataset-name">{filename}</div>
                <div class="dataset-meta">{rows:,} rows · {cols} columns · ID: <code style="font-family:var(--font-mono);font-size:0.75rem;">{ds_id[:8]}…</code></div>
            </div>
            <div><span class="tag">{ext}</span></div>
        </div>""",
        unsafe_allow_html=True,
    )

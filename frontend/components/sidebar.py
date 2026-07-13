"""
frontend/components/sidebar.py
===============================
Reusable sidebar UI components — improved version.
"""

import streamlit as st
from datetime import datetime


def render_session_info():
    """Display current session information in sidebar."""
    with st.sidebar:
        st.divider()
        st.caption("📊 Session Info")
        session_id = st.session_state.get("session_id", "unknown")
        st.code(session_id[:12] + "...", language="text")
        st.caption(f"Started: {datetime.now().strftime('%H:%M:%S')}")


def render_dataset_selector():
    """Render dataset selection dropdown."""
    with st.sidebar:
        datasets = st.session_state.get("uploaded_datasets", {})
        if not datasets:
            return None
        st.markdown(
            '<div style="font-size:0.72rem;font-weight:700;color:#4d6082;text-transform:uppercase;'
            'letter-spacing:0.08em;margin-bottom:8px;">Active Dataset</div>',
            unsafe_allow_html=True,
        )
        selected = st.selectbox(
            "Select dataset",
            options=list(datasets.keys()),
            format_func=lambda x: datasets[x].get("filename", x),
            key="sidebar_dataset_selector",
            label_visibility="collapsed",
        )
        return selected


def render_navigation_menu():
    """Render navigation menu."""
    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;color:#4d6082;text-transform:uppercase;'
        'letter-spacing:0.08em;margin-bottom:8px;">Navigate</div>',
        unsafe_allow_html=True,
    )

    nav_pages = {
        "📤 Upload": "01_upload",
        "🔍 Analyze": "02_analyze",
        "📊 Dashboard": "03_dashboard",
        "📄 RAG Documents": "04_rag",
        "📑 Reports": "05_reports",
        "💬 Chat": "06_chat",
        "🔮 Forecast": "07_forecast",
    }

    def _navigate_to_page():
        st.session_state.nav_page_target = st.session_state.nav_selectbox

    selected = st.selectbox(
        "Go to page",
        options=list(nav_pages.keys()),
        label_visibility="collapsed",
        key="nav_selectbox",
        on_change=_navigate_to_page,
    )

    if st.session_state.get("nav_page_target"):
        page_path = f"pages/{nav_pages[st.session_state.pop('nav_page_target')]}.py"
        st.switch_page(page_path)


def render_settings():
    """Render settings section."""
    with st.sidebar:
        st.divider()
        with st.expander("⚙️ Settings"):
            debug_mode = st.checkbox("Debug Mode", value=False)
            st.session_state["debug_mode"] = debug_mode
            if debug_mode:
                st.markdown("**Session State:**")
                st.write(dict(st.session_state))


def render_help():
    """Render help section."""
    with st.sidebar:
        with st.expander("❓ Help"):
            st.markdown("""
            **Getting Started:**
            1. **Upload** your data (CSV, Excel, JSON)
            2. **Analyze** using natural language
            3. View **Dashboard** for visuals
            4. Upload docs for **RAG**
            5. Generate **Reports**
            6. Use **Chat** for follow-ups
            7. Run **Forecasts**
            """)


def render_full_sidebar():
    """Render the complete sidebar with all components."""
    with st.sidebar:
        # ── Branding ──────────────────────────────────────────────────────────
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

        # ── Session card ─────────────────────────────────────────────────────
        sid = st.session_state.get("session_id", "")
        n_ds = len(st.session_state.get("uploaded_datasets", {}))
        has_analysis = st.session_state.get("last_analysis") is not None

        st.markdown(
            f"""<div style="background:#0c1120;border:1px solid rgba(91,108,245,0.15);
                            border-radius:12px;padding:12px 14px;margin-bottom:16px;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
                    <div>
                        <div style="font-size:0.65rem;color:#4d6082;text-transform:uppercase;
                                    letter-spacing:0.08em;font-weight:700;">Session</div>
                        <div style="font-size:0.78rem;color:#818cf8;font-family:'JetBrains Mono',monospace;
                                    margin-top:2px;">{sid[:12] if sid else 'loading'}…</div>
                    </div>
                    <div style="display:flex;gap:8px;flex-shrink:0;">
                        <div style="text-align:center;">
                            <div style="font-size:1.1rem;font-weight:700;color:#818cf8;">{n_ds}</div>
                            <div style="font-size:0.6rem;color:#4d6082;">DS</div>
                        </div>
                        <div style="text-align:center;">
                            <div style="font-size:1.1rem;font-weight:700;
                                        color:{'#34d399' if has_analysis else '#4d6082'};">
                                {'✓' if has_analysis else '—'}
                            </div>
                            <div style="font-size:0.6rem;color:#4d6082;">AI</div>
                        </div>
                    </div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        st.divider()
        render_navigation_menu()
        st.divider()

        datasets = st.session_state.get("uploaded_datasets", {})
        if datasets:
            render_dataset_selector()
            st.divider()

        render_help()

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("↺ Refresh", width="stretch"):
                st.rerun()
        with col2:
            if st.button("⌂ Home", width="stretch"):
                st.switch_page("app.py")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑 New Session", width="stretch"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

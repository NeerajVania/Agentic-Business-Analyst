"""
frontend/pages/05_reports.py
=============================
Report viewer and download page.
Endpoints: POST /generate-report | GET /generate-report/download/{session_id}
ReportRequest: { session_id, format }
ReportResponse: { session_id, format, content, file_path }
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import streamlit.components.v1 as components
from styles import inject_css, API_BASE, PUBLIC_API_BASE, page_header, section_title
import api_client as api

st.set_page_config(page_title="Reports", page_icon="📑", layout="wide")
inject_css()
from components.sidebar import render_full_sidebar
render_full_sidebar()

page_header("📑", "Reports",
            "View and download professional reports from your analysis sessions")

if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())
if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = None

session_id = st.session_state.session_id
result = st.session_state.last_analysis

# ── Layout ────────────────────────────────────────────────────────────────────
left_col, right_col = st.columns([2, 1], gap="large")

with right_col:
    st.markdown(
        """<div class="ui-card">
            <div style="font-weight:700;color:#f0f4ff;margin-bottom:16px;">Generate Report</div>""",
        unsafe_allow_html=True,
    )
    fmt = st.selectbox(
        "Format",
        ["html", "markdown", "pdf"],
        format_func=lambda x: {"html": "🌐 HTML", "markdown": "📝 Markdown", "pdf": "📄 PDF"}[x],
    )

    fmt_desc = {
        "html": "Rich interactive report with charts",
        "markdown": "Portable Markdown for docs & wikis",
        "pdf": "Print-ready executive PDF report",
    }
    st.markdown(
        f'<div style="color:#4d6082;font-size:0.78rem;margin:-4px 0 12px;">{fmt_desc[fmt]}</div>',
        unsafe_allow_html=True,
    )

    gen_btn = st.button("📄 Generate", type="primary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if gen_btn:
        with st.spinner("Generating report…"):
            try:
                # POST /generate-report — ReportRequest: { session_id, format }
                resp = api.post(
                    "/generate-report",
                    json={"session_id": session_id, "format": fmt},
                    timeout=60,
                )
                ok, data = api.safe_json(resp)

                if ok:
                    # ReportResponse: { session_id, format, content, file_path }
                    st.markdown(
                        '<div class="pill pill-success" style="margin:10px 0;">✅ Report ready!</div>',
                        unsafe_allow_html=True,
                    )
                    ext_map = {"html": "html", "markdown": "md", "pdf": "pdf"}
                    if data.get("content"):
                        # HTML / Markdown — content returned inline
                        st.download_button(
                            f"⬇️ Download {fmt.upper()}",
                            data=data["content"],
                            file_name=f"report_{session_id[:8]}.{ext_map[fmt]}",
                            use_container_width=True,
                        )
                    elif fmt == "pdf" and data.get("file_path"):
                        # PDF — backend stores the file; fetch bytes via the download endpoint
                        try:
                            dl_resp = api.get(
                                f"/generate-report/download/{session_id}",
                                params={"format": "pdf"},
                                timeout=60,
                            )
                            if dl_resp.status_code == 200:
                                st.download_button(
                                    "⬇️ Download PDF",
                                    data=dl_resp.content,
                                    file_name=f"report_{session_id[:8]}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                )
                            else:
                                st.info(
                                    f"PDF saved server-side.\n"
                                    f"Use the **PDF Report** link in the Direct Download Links card below."
                                )
                        except Exception as pdf_err:
                            st.warning(f"Could not fetch PDF bytes: {pdf_err}")
                    elif data.get("file_path"):
                        st.info("Report saved — use the Direct Download Links below.")
                else:
                    # 404 means no analysis has been run yet — surface clearly
                    if resp.status_code == 404 or "not found" in str(data).lower():
                        st.warning("No report found — run an analysis first via the **Analyze** page.")
                    else:
                        st.error(f"Report generation failed: {data}")
            except Exception as e:
                st.error(str(e))

    # ── Direct download links — GET /generate-report/download/{session_id}?format=X
    st.markdown(
        """<div class="ui-card" style="padding:18px 20px;">
            <div style="font-weight:700;color:#f0f4ff;margin-bottom:14px;font-size:0.88rem;">
                Direct Download Links
            </div>""",
        unsafe_allow_html=True,
    )
    for fmt_dl, icon, label in [
        ("html", "🌐", "HTML Report"),
        ("markdown", "📝", "Markdown Report"),
        ("pdf", "📄", "PDF Report"),
    ]:
        # PUBLIC_API_BASE resolves to localhost:8000 even inside Docker,
        # so the link works in the user's browser.
        dl_url = f"{PUBLIC_API_BASE}/generate-report/download/{session_id}?format={fmt_dl}"
        st.markdown(
            f'<a href="{dl_url}" target="_blank" '
            f'style="display:flex;align-items:center;gap:10px;padding:9px 12px;'
            f'background:rgba(91,108,245,0.06);border:1px solid rgba(91,108,245,0.12);'
            f'border-radius:8px;margin-bottom:6px;color:#818cf8;'
            f'text-decoration:none;font-size:0.85rem;font-weight:500;">'
            f'{icon} {label}</a>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with left_col:
    # If last_analysis has report_markdown preview it inline
    if result and result.get("report_markdown"):
        tab1, tab2 = st.tabs(["📝 Markdown Preview", "🌐 HTML Preview"])

        with tab1:
            st.markdown(
                '<div class="ui-card" style="max-height:680px;overflow-y:auto;padding:28px 32px;">',
                unsafe_allow_html=True,
            )
            st.markdown(result["report_markdown"])
            st.markdown("</div>", unsafe_allow_html=True)

        with tab2:
            try:
                # Try to fetch the HTML version from backend
                resp = api.post(
                    "/generate-report",
                    json={"session_id": session_id, "format": "html"},
                    timeout=30,
                )
                ok, data = api.safe_json(resp)
                if ok and data.get("content"):
                    components.html(data["content"], height=680, scrolling=True)
                else:
                    st.markdown(
                        '<div style="text-align:center;padding:40px;color:#4d6082;">HTML preview unavailable — run an analysis first.</div>',
                        unsafe_allow_html=True,
                    )
            except Exception:
                st.markdown(
                    '<div style="text-align:center;padding:40px;color:#4d6082;">HTML preview unavailable.</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.markdown(
            """<div class="ui-card" style="text-align:center;padding:64px 40px;">
                <div style="font-size:3rem;margin-bottom:16px;opacity:0.35;">📑</div>
                <div style="color:#f0f4ff;font-weight:700;margin-bottom:10px;font-size:1.05rem;">
                    No report available yet
                </div>
                <div style="color:#9daec8;font-size:0.88rem;max-width:360px;margin:0 auto;line-height:1.6;">
                    Run an analysis on the <b style="color:#818cf8;">Analyze</b> page first,
                    then use the Generate button to create your executive report.
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

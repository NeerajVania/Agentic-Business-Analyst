"""
frontend/pages/01_upload.py
============================
Dataset upload page — POST /upload/multi  |  DELETE /upload/{id}  |  GET /upload/datasets
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from styles import inject_css, API_BASE, page_header, section_title, dataset_card
import api_client as api

st.set_page_config(page_title="Upload Datasets", page_icon="📤", layout="wide")
inject_css()
from components.sidebar import render_full_sidebar
render_full_sidebar()

page_header("📤", "Upload Datasets",
            "Supports CSV, Excel (.xlsx/.xls) and JSON — upload multiple files for cross-dataset analysis")

if "uploaded_datasets" not in st.session_state:
    st.session_state.uploaded_datasets = {}

# ── Layout ─────────────────────────────────────────────────────────────────────
left_col, right_col = st.columns([3, 2], gap="large")

with left_col:
    st.markdown(
        """<div class="upload-zone">
            <div style="font-size:2.2rem;margin-bottom:10px;
                        filter:drop-shadow(0 0 16px rgba(91,108,245,0.4));">📂</div>
            <div style="color:#f0f4ff;font-weight:600;font-size:0.95rem;margin-bottom:6px;">
                Drop files here or click to browse
            </div>
            <div style="color:#4d6082;font-size:0.78rem;">CSV · XLSX · XLS · JSON accepted</div>
        </div>""",
        unsafe_allow_html=True,
    )
    uploaded_files = st.file_uploader(
        "Drop files here or click to browse",
        type=["csv", "xlsx", "xls", "json"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin:14px 0 8px;">'
            f'<span class="pill pill-info">📁 {len(uploaded_files)} file(s) selected</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        for f in uploaded_files:
            size_kb = len(f.getvalue()) / 1024
            ext = f.name.rsplit(".", 1)[-1].upper() if "." in f.name else "?"
            icon = {"CSV": "📊", "XLSX": "📗", "XLS": "📗", "JSON": "📋"}.get(ext, "📄")
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;padding:9px 14px;'
                f'background:rgba(91,108,245,0.05);border:1px solid rgba(91,108,245,0.1);'
                f'border-radius:8px;margin-bottom:6px;">'
                f'<span style="font-size:1.1rem;">{icon}</span>'
                f'<span style="color:#f0f4ff;font-size:0.87rem;font-weight:500;flex:1;">{f.name}</span>'
                f'<span style="color:#4d6082;font-size:0.75rem;">{size_kb:.1f} KB</span>'
                f'<span class="tag">{ext}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
    upload_btn = st.button(
        "🚀 Upload & Process",
        type="primary",
        width="stretch",
        disabled=not bool(uploaded_files),
    )

with right_col:
    st.markdown(
        """<div class="ui-card">
            <div style="font-weight:700;color:#f0f4ff;margin-bottom:16px;font-size:0.95rem;">
                What happens on upload?
            </div>
            <div class="step-item">
                <div class="step-num">1</div>
                <div class="step-text">Schema detection — column types inferred automatically</div>
            </div>
            <div class="step-item">
                <div class="step-num">2</div>
                <div class="step-text">Primary key identification across all datasets</div>
            </div>
            <div class="step-item">
                <div class="step-num">3</div>
                <div class="step-text">Join suggestions generated for multi-dataset analysis</div>
            </div>
            <div class="step-item">
                <div class="step-num">4</div>
                <div class="step-text">Dataset stored in-memory for the agent pipeline</div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """<div class="ui-card" style="padding:18px 20px;">
            <div style="font-weight:700;color:#f0f4ff;margin-bottom:12px;font-size:0.88rem;">
                Supported Formats
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <div style="display:flex;align-items:center;gap:8px;padding:8px 10px;
                            background:rgba(91,108,245,0.06);border-radius:8px;">
                    <span>📊</span>
                    <div>
                        <div style="color:#f0f4ff;font-size:0.8rem;font-weight:600;">CSV</div>
                        <div style="color:#4d6082;font-size:0.7rem;">Comma-separated</div>
                    </div>
                </div>
                <div style="display:flex;align-items:center;gap:8px;padding:8px 10px;
                            background:rgba(91,108,245,0.06);border-radius:8px;">
                    <span>📗</span>
                    <div>
                        <div style="color:#f0f4ff;font-size:0.8rem;font-weight:600;">Excel</div>
                        <div style="color:#4d6082;font-size:0.7rem;">.xlsx / .xls</div>
                    </div>
                </div>
                <div style="display:flex;align-items:center;gap:8px;padding:8px 10px;
                            background:rgba(91,108,245,0.06);border-radius:8px;">
                    <span>📋</span>
                    <div>
                        <div style="color:#f0f4ff;font-size:0.8rem;font-weight:600;">JSON</div>
                        <div style="color:#4d6082;font-size:0.7rem;">Structured data</div>
                    </div>
                </div>
                <div style="display:flex;align-items:center;gap:8px;padding:8px 10px;
                            background:rgba(91,108,245,0.06);border-radius:8px;">
                    <span>🔗</span>
                    <div>
                        <div style="color:#f0f4ff;font-size:0.8rem;font-weight:600;">Multi-file</div>
                        <div style="color:#4d6082;font-size:0.7rem;">Cross-join analysis</div>
                    </div>
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

# ── Handle upload ──────────────────────────────────────────────────────────────
if upload_btn and uploaded_files:
    progress_bar = st.progress(0, text="Preparing upload…")
    with st.spinner("Uploading and inferring schemas…"):
        files = [("files", (f.name, f.getvalue(), f.type)) for f in uploaded_files]
        progress_bar.progress(30, text="Sending files to backend…")
        try:
            resp = api.post("/upload/multi", files=files, timeout=300)
            ok, data = api.safe_json(resp)

            if not ok:
                progress_bar.empty()
                st.error(f"Upload failed: {data}")
            else:
                progress_bar.progress(80, text="Processing schemas…")

                if "_raw_files" not in st.session_state:
                    st.session_state._raw_files = {}
                for f, ds in zip(uploaded_files, data["datasets"]):
                    st.session_state.uploaded_datasets[ds["dataset_id"]] = ds
                    st.session_state._raw_files[ds["dataset_id"]] = (f.name, f.getvalue(), f.type or "application/octet-stream")

                progress_bar.progress(100, text="Done!")

                st.markdown(
                    f'<div class="pill pill-success" style="margin:16px 0;">'
                    f'✅ Uploaded {len(data["datasets"])} dataset(s) successfully</div>',
                    unsafe_allow_html=True,
                )

                for ds in data["datasets"]:
                    with st.expander(f"📋 {ds['filename']}  ·  {ds['rows']:,} rows × {ds['columns']} cols"):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown(
                                '<div style="font-size:0.72rem;font-weight:700;color:#4d6082;'
                                'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">Schema</div>',
                                unsafe_allow_html=True,
                            )
                            st.json(ds["schema"])
                        with col_b:
                            st.markdown(
                                '<div style="font-size:0.72rem;font-weight:700;color:#4d6082;'
                                'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">Dataset ID</div>',
                                unsafe_allow_html=True,
                            )
                            st.code(ds["dataset_id"], language="text")

                if data.get("join_suggestions"):
                    st.markdown("<br>", unsafe_allow_html=True)
                    section_title("🔗 Suggested Joins")
                    for j in data["join_suggestions"]:
                        cols_list = ", ".join(f"`{c}`" for c in j["common_columns"])
                        conf = j.get("confidence", "medium")
                        badge_cls = {"high": "pill-success", "medium": "pill-warning", "low": "pill-error"}.get(
                            conf.lower(), "pill-info"
                        )
                        st.markdown(
                            f'<div class="ui-card" style="padding:14px 18px;">'
                            f'<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">'
                            f'<span style="color:#818cf8;font-weight:700;font-size:0.9rem;">{j["dataset_a"]}</span>'
                            f'<span style="color:#4d6082;font-size:1rem;">↔</span>'
                            f'<span style="color:#818cf8;font-weight:700;font-size:0.9rem;">{j["dataset_b"]}</span>'
                            f'<span class="pill {badge_cls}" style="margin-left:auto;">{conf} confidence</span>'
                            f'</div>'
                            f'<div style="color:#9daec8;font-size:0.8rem;margin-top:8px;">'
                            f'Common columns: {cols_list}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

        except Exception as e:
            progress_bar.empty()
            st.error(f"Upload failed: {e}")

# ── Loaded datasets ────────────────────────────────────────────────────────────
st.divider()

if st.session_state.uploaded_datasets:
    header_col, btn_col = st.columns([3, 1])
    with header_col:
        section_title(f"📂 Loaded Datasets ({len(st.session_state.uploaded_datasets)})")
    with btn_col:
        if st.button("🗑 Clear All", width="stretch"):
            # Delete from backend too
            for ds_id in list(st.session_state.uploaded_datasets.keys()):
                try:
                    api.delete(f"/upload/{ds_id}", timeout=5)
                except Exception:
                    pass
            st.session_state.uploaded_datasets = {}
            st.rerun()

    for ds_id, meta in list(st.session_state.uploaded_datasets.items()):
        row_a, row_b = st.columns([5, 1])
        with row_a:
            dataset_card(meta["filename"], meta["rows"], meta["columns"], ds_id)
        with row_b:
            if st.button("🗑", key=f"del_{ds_id}", help="Remove dataset"):
                try:
                    api.delete(f"/upload/{ds_id}", timeout=5)
                except Exception:
                    pass
                del st.session_state.uploaded_datasets[ds_id]
                st.rerun()

    st.markdown(
        f"""<div style="background:rgba(91,108,245,0.06);border:1px solid rgba(91,108,245,0.15);
                        border-radius:12px;padding:14px 18px;margin-top:8px;
                        display:flex;align-items:center;gap:12px;">
            <div style="font-size:1.2rem;">💡</div>
            <div style="color:#9daec8;font-size:0.85rem;line-height:1.5;">
                Datasets loaded! Head to
                <b style="color:#818cf8;">Analyze</b> to ask business questions
                or <b style="color:#818cf8;">Dashboard</b> to explore visuals.
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """<div style="text-align:center;padding:48px 24px;">
            <div style="font-size:2.5rem;margin-bottom:12px;opacity:0.4;">📂</div>
            <div style="color:#9daec8;font-weight:600;margin-bottom:6px;">No datasets loaded yet</div>
            <div style="color:#4d6082;font-size:0.85rem;">Upload files above to get started.</div>
        </div>""",
        unsafe_allow_html=True,
    )

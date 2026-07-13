"""
frontend/pages/04_rag.py
=========================
RAG document upload and knowledge-base query interface.
Endpoints: POST /rag/upload | POST /rag/query | GET /rag/status
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from styles import inject_css, page_header, section_title, kpi_row
import api_client as api

st.set_page_config(page_title="RAG Knowledge Base", page_icon="📚", layout="wide")
inject_css()
from components.sidebar import render_full_sidebar
render_full_sidebar()

page_header("📚", "RAG Knowledge Base",
            "Upload company documents and retrieve contextual answers via semantic search")

if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())

tab1, tab2, tab3 = st.tabs(["📤 Ingest Documents", "🔍 Query Knowledge", "📊 Collection Status"])

# ── Upload tab ─────────────────────────────────────────────────────────────────
with tab1:
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown(
            """<div class="upload-zone">
                <div style="font-size:2rem;margin-bottom:10px;
                            filter:drop-shadow(0 0 16px rgba(91,108,245,0.35));">📄</div>
                <div style="color:#f0f4ff;font-weight:600;margin-bottom:6px;">
                    Drop document here or click to browse
                </div>
                <div style="color:#4d6082;font-size:0.78rem;">PDF · DOCX · TXT · Markdown</div>
            </div>""",
            unsafe_allow_html=True,
        )
        rag_file = st.file_uploader(
            "Choose a document",
            type=["pdf", "docx", "txt", "md"],
            label_visibility="collapsed",
        )

        if rag_file:
            size_kb = len(rag_file.getvalue()) / 1024
            ext = rag_file.name.rsplit(".", 1)[-1].upper() if "." in rag_file.name else "?"
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;padding:12px 14px;'
                f'background:rgba(91,108,245,0.06);border:1px solid rgba(91,108,245,0.15);'
                f'border-radius:10px;margin:12px 0;">'
                f'<span style="font-size:1.3rem;">📎</span>'
                f'<span style="color:#f0f4ff;font-weight:500;flex:1;">{rag_file.name}</span>'
                f'<span style="color:#4d6082;font-size:0.75rem;">{size_kb:.1f} KB</span>'
                f'<span class="tag">{ext}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        ingest_btn = st.button(
            "📥 Ingest Document",
            type="primary",
            width="stretch",
            disabled=not bool(rag_file),
        )

        if ingest_btn and rag_file:
            progress = st.progress(0, text="Loading document…")
            with st.spinner("Loading → Chunking → Embedding…"):
                try:
                    progress.progress(20, text="Chunking document…")
                    # POST /rag/upload — multipart file
                    resp = api.post(
                        "/rag/upload",
                        files={"file": (rag_file.name, rag_file.getvalue(), rag_file.type)},
                        timeout=120,
                    )
                    progress.progress(70, text="Generating embeddings…")
                    ok, data = api.safe_json(resp)

                    if not ok:
                        progress.empty()
                        st.error(f"Ingest failed: {data}")
                    else:
                        progress.progress(100, text="Stored in vector index!")
                        # RAGUploadResponse: { filename, chunks_stored, collection }
                        st.markdown(
                            f'<div class="pill pill-success" style="margin:14px 0;">'
                            f'✅ Ingested <b>{data["filename"]}</b> — {data["chunks_stored"]} chunks stored</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f'<div style="color:#4d6082;font-size:0.78rem;">Collection: '
                            f'<code style="font-family:var(--font-mono);">{data["collection"]}</code></div>',
                            unsafe_allow_html=True,
                        )
                except Exception as e:
                    progress.empty()
                    st.error(f"Ingest failed: {e}")

    with right:
        st.markdown(
            """<div class="ui-card">
                <div style="font-weight:700;color:#f0f4ff;margin-bottom:16px;">RAG Pipeline</div>
                <div class="step-item">
                    <div class="step-num">1</div>
                    <div class="step-text">Document loaded and parsed</div>
                </div>
                <div class="step-item">
                    <div class="step-num">2</div>
                    <div class="step-text">Split into semantic chunks</div>
                </div>
                <div class="step-item">
                    <div class="step-num">3</div>
                    <div class="step-text">HuggingFace embeddings generated</div>
                </div>
                <div class="step-item">
                    <div class="step-num">4</div>
                    <div class="step-text">Stored in ChromaDB vector index</div>
                </div>
                <div class="step-item">
                    <div class="step-num">5</div>
                    <div class="step-text">Available for semantic retrieval</div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        st.markdown(
            """<div class="ui-card" style="padding:18px 20px;">
                <div style="font-weight:700;color:#f0f4ff;margin-bottom:12px;font-size:0.88rem;">
                    Supported Document Types
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:6px;">
                    <span class="tag">PDF</span>
                    <span class="tag">DOCX</span>
                    <span class="tag">TXT</span>
                    <span class="tag">Markdown</span>
                </div>
                <div style="color:#4d6082;font-size:0.78rem;margin-top:12px;line-height:1.5;">
                    Ideal for: SOPs, reports, product docs,<br>
                    policy documents, research papers
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

# ── Query tab ──────────────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="ui-card">', unsafe_allow_html=True)

    left_q, right_q = st.columns([4, 1], gap="large")
    with left_q:
        query = st.text_input(
            "Ask a question about your documents",
            placeholder="e.g. What is our returns policy? What were the Q3 highlights?",
            label_visibility="collapsed",
        )
    with right_q:
        top_k = st.number_input(
            "Chunks", min_value=1, max_value=20, value=5,
            help="Number of chunks to retrieve (top_k in RAGQueryRequest)",
        )

    search_btn = st.button(
        "🔍 Search Knowledge Base",
        type="primary",
        width="stretch",
        disabled=not bool(query),
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if search_btn and query:
        with st.spinner("Retrieving and generating answer…"):
            try:
                # POST /rag/query — RAGQueryRequest: { query, session_id, top_k }
                resp = api.post(
                    "/rag/query",
                    json={
                        "query": query,
                        "session_id": st.session_state.session_id,
                        "top_k": int(top_k),
                    },
                    timeout=60,
                )
                ok, data = api.safe_json(resp)

                if not ok:
                    st.error(f"Query failed: {data}")
                else:
                    # RAGQueryResponse: { answer, citations, session_id }
                    st.markdown(
                        f"""<div class="ui-card" style="background:linear-gradient(135deg,
                                rgba(91,108,245,0.07),rgba(124,58,237,0.05));">
                            <div class="section-title">💬 Answer</div>
                            <div style="color:#e2e8f0;line-height:1.75;font-size:0.92rem;">{data["answer"]}</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                    if data.get("citations"):
                        st.markdown("<br>", unsafe_allow_html=True)
                        section_title(f"📎 Sources ({len(data['citations'])})")
                        for c in data["citations"]:
                            st.markdown(
                                f'<div class="insight-item" style="font-size:0.83rem;">{c}</div>',
                                unsafe_allow_html=True,
                            )

            except Exception as e:
                st.error(f"Query failed: {e}")

# ── Status tab ─────────────────────────────────────────────────────────────────
with tab3:
    col_btn, _ = st.columns([1, 3])
    with col_btn:
        refresh_btn = st.button("🔄 Refresh Status", width="stretch")

    if refresh_btn:
        try:
            # GET /rag/status — returns { collection, document_count }
            resp = api.get("/rag/status", timeout=10)
            ok, data = api.safe_json(resp)
            if ok:
                kpi_row([
                    ("Collection", data.get("collection", "—"), ""),
                    ("Documents Stored", str(data.get("document_count", 0)), ""),
                ])
                if data.get("error"):
                    st.warning(f"Vector store warning: {data['error']}")
            else:
                st.error(f"Could not fetch status: {data}")
        except Exception as e:
            st.error(f"Could not fetch status: {e}")
    else:
        st.markdown(
            """<div style="text-align:center;padding:40px;color:#4d6082;">
                Click <b>Refresh Status</b> to view collection info.
            </div>""",
            unsafe_allow_html=True,
        )

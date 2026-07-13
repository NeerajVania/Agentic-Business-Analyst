"""
frontend/pages/06_chat.py
=========================
Conversational chat interface with RAG and conversation history.
Endpoint: POST /chat
ChatRequest:  { message, session_id }
ChatResponse: { response, session_id, rag_citations }
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from datetime import datetime
from styles import inject_css, page_header
import api_client as api

st.set_page_config(page_title="Chat Assistant", page_icon="💬", layout="wide")
inject_css()

# ── Extra chat-specific CSS ────────────────────────────────────────────────────
st.markdown("""
<style>
.chat-viewport {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 20px 0;
    max-height: 560px;
    overflow-y: auto;
}
.msg-row {
    display: flex;
    gap: 10px;
    align-items: flex-end;
    animation: msg-in 0.28s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
.msg-row.user { flex-direction: row-reverse; }
@keyframes msg-in {
    from { opacity: 0; transform: translateY(14px) scale(0.97); }
    to   { opacity: 1; transform: translateY(0)   scale(1); }
}
.avatar {
    width: 34px; height: 34px;
    border-radius: 50%;
    flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.9rem;
    font-weight: 700;
}
.avatar-ai  { background: linear-gradient(135deg, #5b6cf5, #7c3aed); box-shadow: 0 2px 10px rgba(91,108,245,0.35); }
.avatar-usr { background: linear-gradient(135deg, #0891b2, #0ea57a); box-shadow: 0 2px 10px rgba(8,145,178,0.35); }
.bubble {
    max-width: 72%;
    padding: 13px 17px;
    border-radius: 18px;
    font-size: 0.9rem;
    line-height: 1.65;
    word-break: break-word;
}
.bubble-ai {
    background: #111827;
    border: 1px solid rgba(91,108,245,0.18);
    color: #e2e8f0;
    border-radius: 4px 18px 18px 18px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.3);
}
.bubble-user {
    background: linear-gradient(135deg, #5b6cf5, #7c3aed);
    color: #fff;
    border-radius: 18px 18px 4px 18px;
    box-shadow: 0 4px 16px rgba(91,108,245,0.35);
}
.msg-ts {
    font-size: 0.67rem;
    color: #4d6082;
    margin-top: 5px;
    display: block;
    text-align: right;
}
.msg-row.user .msg-ts { text-align: left; }
.cit-chip {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(91,108,245,0.09);
    border: 1px solid rgba(91,108,245,0.2);
    border-radius: 6px;
    padding: 3px 9px;
    font-size: 0.73rem;
    color: #818cf8;
    margin: 3px 3px 0 0;
}
.chat-empty {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 60px 24px;
    text-align: center;
    color: #4d6082;
}
.chat-empty .brain { font-size: 3.5rem; margin-bottom: 14px; filter: drop-shadow(0 0 24px rgba(91,108,245,0.4)); }
.chat-empty h3 { color: #9daec8; font-size: 1rem; margin: 0 0 8px; font-weight: 600; }
.chat-empty p  { font-size: 0.85rem; max-width: 320px; line-height: 1.6; margin: 0; }
.chip-row { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 18px; justify-content: center; }
.chip {
    background: rgba(91,108,245,0.08);
    border: 1px solid rgba(91,108,245,0.2);
    border-radius: 999px;
    padding: 7px 16px;
    font-size: 0.8rem;
    color: #818cf8;
    font-weight: 500;
}
.ctx-card {
    background: #0c1120;
    border: 1px solid rgba(91,108,245,0.12);
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.ctx-label {
    font-size: 0.65rem;
    font-weight: 700;
    color: #4d6082;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    margin-bottom: 8px;
}
.ctx-stat {
    font-size: 1.6rem;
    font-weight: 800;
    color: #818cf8;
    font-family: 'Syne', sans-serif;
    line-height: 1;
}
.ctx-sub { font-size: 0.72rem; color: #4d6082; margin-top: 3px; }
div[data-testid="stButton"] > button[kind="secondary"] {
    background: rgba(91,108,245,0.06) !important;
    border: 1px solid rgba(91,108,245,0.18) !important;
    color: #9daec8 !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    text-align: left !important;
}
div[data-testid="stButton"] > button[kind="secondary"]:hover {
    background: rgba(91,108,245,0.14) !important;
    border-color: rgba(91,108,245,0.4) !important;
    color: #f0f4ff !important;
}
.typing-indicator { display: flex; gap: 5px; padding: 14px 18px; }
.typing-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #5b6cf5;
    animation: typing 1.2s infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
    0%, 80%, 100% { transform: scale(0.7); opacity: 0.4; }
    40%           { transform: scale(1.1); opacity: 1; }
}
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "uploaded_datasets" not in st.session_state:
    st.session_state.uploaded_datasets = {}

from components.sidebar import render_full_sidebar
render_full_sidebar()

page_header("💬", "Chat Assistant",
            "Ask questions about your data and company knowledge — powered by Mistral AI + RAG")

chat_col, ctx_col = st.columns([3, 1], gap="large")

# ── Context / control panel ────────────────────────────────────────────────────
with ctx_col:
    n_msgs  = len(st.session_state.chat_messages)
    n_ds    = len(st.session_state.uploaded_datasets)
    has_rag = st.session_state.get("last_analysis") is not None

    st.markdown(
        f"""<div class="ctx-card">
            <div class="ctx-label">Session stats</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                <div>
                    <div class="ctx-stat">{n_msgs}</div>
                    <div class="ctx-sub">Total messages</div>
                </div>
                <div>
                    <div class="ctx-stat">{n_ds}</div>
                    <div class="ctx-sub">Datasets</div>
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    rag_color = "#34d399" if has_rag else "#4d6082"
    rag_label = "Analysis loaded" if has_rag else "No analysis yet"
    st.markdown(
        f"""<div class="ctx-card">
            <div class="ctx-label">Knowledge context</div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <div style="width:8px;height:8px;border-radius:50%;background:{rag_color};
                            box-shadow:0 0 6px {rag_color};"></div>
                <span style="font-size:0.8rem;color:{rag_color};font-weight:600;">{rag_label}</span>
            </div>
            <div style="font-size:0.73rem;color:#4d6082;line-height:1.5;">
                RAG retrieves relevant chunks from your uploaded documents to ground answers.
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="font-size:0.65rem;font-weight:700;color:#4d6082;'
        'text-transform:uppercase;letter-spacing:0.09em;margin:14px 0 8px;">Actions</div>',
        unsafe_allow_html=True,
    )

    if st.button("🗑️ Clear History", width="stretch"):
        st.session_state.chat_messages = []
        st.rerun()

    if st.session_state.chat_messages:
        msgs = st.session_state.chat_messages
        content = "\n\n".join(
            f"**{m['role'].upper()}** ({m.get('timestamp', '')[:19]})\n{m['content']}"
            for m in msgs
        )
        st.download_button(
            "⬇️ Export Chat (.md)",
            data=content,
            file_name="chat_export.md",
            mime="text/markdown",
            width="stretch",
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.65rem;font-weight:700;color:#4d6082;'
        'text-transform:uppercase;letter-spacing:0.09em;margin-bottom:8px;">Quick Prompts</div>',
        unsafe_allow_html=True,
    )
    suggestions = [
        "📊 Summarize my dataset",
        "📈 What are the main trends?",
        "⚠️ Detect any anomalies",
        "💡 Give me recommendations",
        "📋 Explain the executive summary",
        "🔍 Which metric needs attention?",
    ]
    for sug in suggestions:
        clean = sug.split(" ", 1)[1] if " " in sug else sug
        if st.button(sug, width="stretch", key=f"sug_{sug}"):
            st.session_state["_pending_prompt"] = clean
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """<div class="ctx-card">
            <div class="ctx-label">Tips</div>
            <div style="color:#4d6082;font-size:0.79rem;line-height:1.7;">
                • Ask follow-ups to drill down<br>
                • Reference columns by name<br>
                • Request charts &amp; tables<br>
                • Ask "why" for deeper insight
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

# ── Main chat area ─────────────────────────────────────────────────────────────
with chat_col:
    st.markdown('<div class="ui-card" style="padding:0;overflow:hidden;">', unsafe_allow_html=True)

    st.markdown(
        f"""<div style="padding:14px 20px;border-bottom:1px solid rgba(91,108,245,0.12);
                        background:rgba(11,16,34,0.8);display:flex;align-items:center;gap:12px;">
            <div class="avatar avatar-ai" style="width:28px;height:28px;font-size:0.8rem;">🧠</div>
            <div>
                <div style="color:#f0f4ff;font-weight:700;font-size:0.9rem;">Agentic Analyst</div>
                <div style="display:flex;align-items:center;gap:5px;margin-top:1px;">
                    <span class="status-dot"></span>
                    <span style="color:#34d399;font-size:0.7rem;font-weight:600;">Online</span>
                    <span style="color:#4d6082;font-size:0.7rem;">· Mistral AI + RAG</span>
                </div>
            </div>
            <div style="margin-left:auto;font-size:0.72rem;color:#4d6082;">
                {n_msgs} message{'s' if n_msgs != 1 else ''}
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    messages = st.session_state.chat_messages

    if not messages:
        st.markdown(
            """<div class="chat-empty">
                <div class="brain">🤖</div>
                <h3>Hello! I'm your AI Analyst</h3>
                <p>Ask me anything about your datasets, company documents, or business insights.
                   I combine data analysis with RAG-powered knowledge retrieval.</p>
                <div class="chip-row">
                    <span class="chip">📊 Analyze trends</span>
                    <span class="chip">💡 Get recommendations</span>
                    <span class="chip">⚠️ Find anomalies</span>
                    <span class="chip">📋 Summarize data</span>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="chat-viewport">', unsafe_allow_html=True)
        for message in messages:
            is_user = message["role"] == "user"
            row_cls    = "msg-row user" if is_user else "msg-row"
            avatar_cls = "avatar avatar-usr" if is_user else "avatar avatar-ai"
            avatar_icon = "👤" if is_user else "🧠"
            bubble_cls = "bubble bubble-user" if is_user else "bubble bubble-ai"
            ts = message.get("timestamp", "")[:19].replace("T", " ")

            # rag_citations come from ChatResponse.rag_citations
            citations_html = ""
            if message.get("citations"):
                chips = "".join(
                    f'<span class="cit-chip">📎 {c[:60]}{"…" if len(c) > 60 else ""}</span>'
                    for c in message["citations"][:4]
                )
                citations_html = f'<div style="margin-top:8px;">{chips}</div>'

            st.markdown(
                f"""<div class="{row_cls}">
                    <div class="{avatar_cls}">{avatar_icon}</div>
                    <div style="max-width:72%;">
                        <div class="{bubble_cls}">{message['content']}{citations_html}</div>
                        <span class="msg-ts">{ts}</span>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Input ──────────────────────────────────────────────────────────────────
    pending = st.session_state.pop("_pending_prompt", None)
    user_input = st.chat_input("Ask anything about your data or company knowledge…") or pending

    if user_input:
        ts_now = datetime.now().isoformat()
        st.session_state.chat_messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": ts_now,
        })

        with st.spinner(""):
            st.markdown(
                """<div class="msg-row" style="margin-top:8px;">
                    <div class="avatar avatar-ai">🧠</div>
                    <div class="bubble bubble-ai">
                        <div class="typing-indicator">
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                        </div>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
            try:
                # POST /chat — ChatRequest: { message, session_id }
                resp = api.post(
                    "/chat",
                    json={
                        "message": user_input,
                        "session_id": st.session_state.session_id,
                    },
                    timeout=60,
                )
                ok, data = api.safe_json(resp)

                if ok:
                    # ChatResponse: { response, session_id, rag_citations }
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": data["response"],
                        "citations": data.get("rag_citations", []),
                        "timestamp": datetime.now().isoformat(),
                    })
                    st.rerun()
                else:
                    st.error(f"Chat error: {data}")

            except Exception as e:
                st.error(f"Chat error: {e}")

"""
backend/api/routes_chat.py
==========================
Conversational chat endpoint with Redis-backed memory.

  POST /chat

Frontend consumer
-----------------
  06_chat.py  →  POST /chat
    Payload:  { message: str, session_id: str }
    Expects:  ChatResponse:
                { response: str, session_id: str, rag_citations: list[str] }

    The frontend renders:
      • message["content"]   → bubble text
      • message["citations"] → citation chips (cit-chip CSS class)
      • message["timestamp"] → msg-ts display
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger

from backend.models.schemas import ChatRequest, ChatResponse
from memory.redis_memory import get_memory
from rag.pipeline import rag_answer

try:
    from mistralai.errors import MistralAuthenticationError
except Exception:
    try:
        from mistralai import MistralAuthenticationError
    except Exception:
        MistralAuthenticationError = None

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Conversational chat with rolling memory window.

    Uses RAG for context-aware, document-grounded replies.
    The last 6 messages from the session history are injected as
    conversation context into the RAG prompt.
    """
    memory = get_memory()

    # Retrieve recent conversation turns (max 10 stored, pass last 6 as context)
    history = memory.get_history(request.session_id, limit=10)
    context_str = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history[-6:]
    )

    try:
        from starlette.concurrency import run_in_threadpool
        answer, citations = await run_in_threadpool(
            rag_answer,
            query=request.message,
            data_context=context_str,
        )
    except Exception as exc:
        logger.exception("Chat RAG failed")
        error_message = str(exc) or "Unknown chat error"
        is_auth_error = (
            MistralAuthenticationError is not None
            and isinstance(exc, MistralAuthenticationError)
        )
        if is_auth_error or any(keyword in error_message.lower() for keyword in [
            "authentication",
            "unauthorized",
            "invalid api key",
            "api key",
        ]):
            raise HTTPException(
                status_code=401,
                detail="Mistral authentication failed. Check your MISTRAL_API_KEY.",
            )

        raise HTTPException(
            status_code=500,
            detail="Chat error: Internal Server Error",
        )

    # Persist both turns so follow-up questions have full context
    memory.add_message(request.session_id, "user", request.message)
    memory.add_message(request.session_id, "assistant", answer)

    return ChatResponse(
        response=answer,
        session_id=request.session_id,
        rag_citations=[
            f"{c.get('source', 'unknown')} · p.{c.get('page', '')} · chunk {c.get('chunk_index', '')} · score {c.get('relevance_score', 0):.2f}"
            if isinstance(c, dict) else str(c)
            for c in (citations or [])
        ],
    )
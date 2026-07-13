"""
backend/api/routes_rag.py
==========================
RAG document ingestion and query endpoints.

  POST /rag/upload   — ingest a knowledge document into ChromaDB
  POST /rag/query    — retrieve + generate grounded answer
  GET  /rag/status   — collection doc count

Frontend consumer
-----------------
  04_rag.py  →  POST /rag/upload
    Sends:    multipart file (pdf/docx/txt/md)
    Expects:  RAGUploadResponse:
                { filename, chunks_stored, collection }

  04_rag.py  →  POST /rag/query
    Payload:  { query: str, session_id: str, top_k: int }
    Expects:  RAGQueryResponse:
                { answer: str, citations: list[str], session_id: str }
    The frontend displays:
      • data["answer"]     → answer card
      • data["citations"]  → source list with insight-item CSS class

  04_rag.py  →  GET /rag/status
    Expects:  { collection: str, document_count: int }
    Shown as kpi_row() cards.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger

from backend.models.schemas import RAGUploadResponse, RAGQueryRequest, RAGQueryResponse
from rag.pipeline import ingest_document, rag_answer
from vectorstore.chroma_store import ChromaStore
from config.settings import get_settings

settings = get_settings()
router = APIRouter()

ALLOWED_RAG_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


@router.post("/upload", response_model=RAGUploadResponse)
async def rag_upload(file: UploadFile = File(...)) -> RAGUploadResponse:
    """
    Upload and ingest a knowledge document into the ChromaDB vector store.

    Pipeline: load → chunk → embed (HuggingFace) → store in ChromaDB.
    The temp file is written to settings.upload_dir and deleted after ingestion.
    """
    ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_RAG_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_RAG_EXTENSIONS}",
        )

    temp_path = settings.upload_dir / f"rag_{file.filename}"
    content = await file.read()
    temp_path.write_bytes(content)

    try:
        ingest_result = ingest_document(str(temp_path))
        if not isinstance(ingest_result, dict):
            raise ValueError("RAG ingest returned invalid response type")
        if ingest_result.get("error"):
            raise ValueError(ingest_result["error"])
        if "chunks_stored" not in ingest_result:
            raise ValueError("RAG ingest response missing 'chunks_stored'")

        chunks = ingest_result["chunks_stored"]
        try:
            chunks = int(chunks)
        except (TypeError, ValueError):
            raise ValueError("RAG ingest response 'chunks_stored' must be an integer")

        filename = ingest_result.get("doc_name", file.filename)
        logger.info("RAG ingested '{}' → {} chunks", filename, chunks)
        return RAGUploadResponse(
            filename=filename,
            chunks_stored=chunks,
            collection=settings.chroma_collection,
        )
    except Exception as exc:
        logger.error("RAG ingest failed for '{}': {}", file.filename, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        temp_path.unlink(missing_ok=True)


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest) -> RAGQueryResponse:
    """
    Query the knowledge base and return a cited answer.

    top_k controls how many chunks are retrieved from ChromaDB before
    being passed to the LLM for synthesis.
    """
    try:
        answer, citations = rag_answer(query=request.query, top_k=request.top_k)
        # citations may be list[dict] or list[str] — normalise to list[str]
        str_citations: list[str] = []
        for c in citations or []:
            if isinstance(c, dict):
                source = c.get("source", "unknown")
                page   = c.get("page", "")
                score  = c.get("relevance_score", 0)
                chunk  = c.get("chunk_index", "")
                parts  = [source]
                if page:  parts.append(f"p.{page}")
                if chunk != "": parts.append(f"chunk {chunk}")
                if score: parts.append(f"score {score:.2f}")
                str_citations.append(" · ".join(parts))
            else:
                str_citations.append(str(c))
        return RAGQueryResponse(
            answer=answer,
            citations=str_citations,
            session_id=request.session_id,
        )
    except Exception as exc:
        logger.error("RAG query failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
async def rag_status() -> dict:
    """Return the ChromaDB collection name and document count."""
    try:
        store = ChromaStore()
        count = store.count()
        return {"collection": settings.chroma_collection, "document_count": count}
    except Exception as exc:
        logger.warning("RAG status check failed: {}", exc)
        return {
            "collection": settings.chroma_collection,
            "document_count": 0,
            "error": str(exc),
        }
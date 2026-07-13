"""RAG ingestion and query pipeline.

Functions:
- ingest_document(file_path: str, doc_type: str = "general") -> dict
- query_pipeline(question: str, use_filter: dict = None) -> dict

Stores chunks in ChromaDB collection "business_docs" with metadata and embeddings.
"""
from __future__ import annotations

import os
import uuid
import datetime
from typing import List, Dict, Any, Tuple

import chromadb
from pypdf import PdfReader
from docx import Document as DocxDocument

from rag.retriever import _get_client, COLLECTION_NAME


_EMBED_MODEL = None  # Lazy-loaded on first use


def _get_embed_model():
    """Get or initialize the embedding model (lazy-loaded)."""
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _EMBED_MODEL


def _split_words_to_chunks(text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    n = len(words)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == n:
            break
        start = end - overlap
    return chunks


def _get_collection():
    client = _get_client()
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        try:
            return client.create_collection(name=COLLECTION_NAME)
        except Exception:
            return client.get_collection(COLLECTION_NAME)


def _embed_texts(texts: List[str]) -> List[List[float]]:
    model = _get_embed_model()
    emb = model.encode(texts, normalize_embeddings=True)
    return [e.tolist() for e in emb]


def ingest_document(file_path: str, doc_type: str = "general") -> Dict[str, Any]:
    """Ingest a document (PDF, DOCX, TXT) into ChromaDB.

    Returns: {"chunks_stored": int, "doc_name": str}
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    filename = os.path.basename(file_path)
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    pages_text: List[Tuple[int, str]] = []  # (page_number, text)

    try:
        if ext == ".pdf":
            reader = PdfReader(file_path)
            for i, page in enumerate(reader.pages, start=1):
                try:
                    txt = page.extract_text() or ""
                except Exception:
                    txt = ""
                pages_text.append((i, txt))
        elif ext in (".docx", ".doc"):
            doc = DocxDocument(file_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            pages_text.append((1, "\n".join(full_text)))
        else:
            # treat as text
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read()
            pages_text.append((1, txt))
    except Exception as exc:
        # handle corrupt PDF/etc
        return {"chunks_stored": 0, "doc_name": filename, "error": str(exc)}

    # chunk and prepare for ingestion
    docs: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    ids: List[str] = []

    for page_number, text in pages_text:
        if not text or not text.strip():
            continue
        chunks = _split_words_to_chunks(text, chunk_size=512, overlap=50)
        for idx, chunk in enumerate(chunks):
            docs.append(chunk)
            meta = {
                "source": filename,
                "page_number": page_number,
                "chunk_index": idx,
                "doc_type": doc_type,
                "ingested_at": datetime.datetime.utcnow().isoformat() + "Z",
            }
            metadatas.append(meta)
            ids.append(str(uuid.uuid4()))

    if not docs:
        return {"chunks_stored": 0, "doc_name": filename}

    print(f"Ingesting {filename}... {len(docs)} chunks stored.")

    # create collection and add
    collection = _get_collection()

    embeddings = _embed_texts(docs)

    try:
        # preferred signature
        collection.add(ids=ids, documents=docs, metadatas=metadatas, embeddings=embeddings)
    except TypeError:
        # fallback signatures
        collection.add(documents=docs, metadatas=metadatas, ids=ids)
        # some chroma clients accept embeddings via separate call
        try:
            collection.add(embeddings=embeddings)
        except Exception:
            pass

    return {"chunks_stored": len(docs), "doc_name": filename}


def query_pipeline(question: str, use_filter: dict = None, n_results: int = 5) -> Dict[str, Any]:
    """Retrieve top chunks and return context + citations."""
    from rag.retriever import retrieve, retrieve_with_filter

    if use_filter:
        return retrieve_with_filter(question, metadata_filter=use_filter, n_results=n_results)
    return retrieve(question, n_results=n_results)


def retrieve_context(question: str, use_filter: dict = None, n_results: int = 5) -> Tuple[str, List[Dict[str, Any]]]:
    """Wrapper around query_pipeline that returns (context_string, citations_list).

    Returns tuple of:
      - context_str: Combined context with inline citations
      - citations: List of citation dicts with keys: source, page, chunk_index, relevance_score
    """
    result = query_pipeline(question, use_filter=use_filter, n_results=n_results)
    context_str = result.get("context", "")
    citations = result.get("citations", [])
    return (context_str, citations)

def rag_answer(query: str, data_context: str = "", top_k: int = 5) -> tuple:
    """
    Called by routes_chat.py.
    Returns (answer_string, citations_list).
    """
    # Step 1 — retrieve RAG context
    result = query_pipeline(query, n_results=top_k)
    rag_context = result.get("context", "")
    citations = result.get("citations", [])

    try:
        from mistralai.client import Mistral
    except ImportError:
        try:
            from mistralai import Mistral
        except ImportError:
            Mistral = None

    # Step 2 — build prompt
    system_prompt = (
        "You are a helpful business analyst assistant. "
        "Answer the user's question using the provided context. "
        "If the context doesn't contain relevant information, say so honestly. "
        "Be concise and precise."
    )

    user_message_parts = []
    if rag_context:
        user_message_parts.append(f"Knowledge Base Context:\n{rag_context}")
    if data_context:
        user_message_parts.append(f"Conversation History:\n{data_context}")
    user_message_parts.append(f"Question: {query}")

    user_message = "\n\n".join(user_message_parts)

    # Step 3 — call Mistral
    try:
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            return ("Could not generate answer: MISTRAL_API_KEY not set", citations)
        client = Mistral(api_key=api_key)
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
        )
        answer = response.choices[0].message.content
    except Exception as exc:
        answer = f"Could not generate answer: {exc}"

    return (answer, citations)

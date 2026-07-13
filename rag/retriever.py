"""Citation-aware retriever using ChromaDB and SentenceTransformers.

Provides:
- retrieve(query: str, n_results: int = 5) -> dict
- retrieve_with_filter(query: str, metadata_filter: dict) -> dict

Collection name: "business_docs"
"""
from __future__ import annotations

from typing import List, Dict, Any

import chromadb


_EMBED_MODEL = None  # Lazy-loaded on first use
_CLIENT = None  # Lazy-loaded on first use
COLLECTION_NAME = "business_docs"


def _get_client():
    global _CLIENT
    if _CLIENT is None:
        import os
        path = os.environ.get("VECTORSTORE_DIR", "./data/vectorstore")
        os.makedirs(path, exist_ok=True)
        _CLIENT = chromadb.PersistentClient(path=path)
    return _CLIENT


CLIENT = None  # kept for backward-compat; use _get_client() internally


def _get_embed_model():
    """Get or initialize the embedding model (lazy-loaded)."""
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _EMBED_MODEL


def _get_collection():
    client = _get_client()
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        try:
            return client.create_collection(name=COLLECTION_NAME)
        except Exception:
            return client.get_collection(COLLECTION_NAME)


def _embed_query(query: str) -> List[float]:
    model = _get_embed_model()
    emb = model.encode([query], normalize_embeddings=True)
    return emb[0].tolist()


def _clamp_score(x: float) -> float:
    if x != x:
        return 0.0
    return max(0.0, min(1.0, float(x)))


def retrieve(query: str, n_results: int = 5) -> Dict[str, Any]:
    """Retrieve top chunks for `query` and return context + citations.

    Returns: {"context": str, "citations": [ {source, page, chunk_index, relevance_score} ]}
    """
    try:
        collection = _get_collection()
    except Exception:
        return {"context": "", "citations": []}

    try:
        emb = _embed_query(query)
        results = collection.query(query_embeddings=[emb], n_results=n_results, include=["documents", "metadatas", "distances"]) 
    except Exception:
        return {"context": "", "citations": []}

    try:
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
    except Exception:
        return {"context": "", "citations": []}

    if not documents:
        return {"context": "", "citations": []}

    docs = []
    citations: List[Dict[str, Any]] = []
    for i, text in enumerate(documents):
        meta = metadatas[i] if i < len(metadatas) else {}
        distance = distances[i] if i < len(distances) else 1.0
        relevance = _clamp_score(1.0 - float(distance))

        source = meta.get("source", "unknown")
        page = int(meta.get("page_number", 1)) if meta.get("page_number") is not None else 1
        chunk_index = int(meta.get("chunk_index", 0)) if meta.get("chunk_index") is not None else i

        cited_text = f"{text.strip()} [Source: {source}, p.{page}]"
        docs.append(cited_text)

        citations.append({
            "source": source,
            "page": page,
            "chunk_index": chunk_index,
            "relevance_score": relevance,
        })

    context = "\n\n".join(docs)
    return {"context": context, "citations": citations}


def retrieve_with_filter(query: str, metadata_filter: dict, n_results: int = 5) -> Dict[str, Any]:
    """Retrieve using metadata filter (e.g., {"doc_type": "policy"})."""
    try:
        collection = _get_collection()
    except Exception:
        return {"context": "", "citations": []}

    emb = _embed_query(query)
    try:
        results = collection.query(query_embeddings=[emb], n_results=n_results, where=metadata_filter, include=["documents", "metadatas", "distances"])
    except Exception:
        return {"context": "", "citations": []}

    try:
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
    except Exception:
        return {"context": "", "citations": []}

    if not documents:
        return {"context": "", "citations": []}

    docs = []
    citations = []
    for i, text in enumerate(documents):
        meta = metadatas[i] if i < len(metadatas) else {}
        distance = distances[i] if i < len(distances) else 1.0
        relevance = _clamp_score(1.0 - float(distance))

        source = meta.get("source", "unknown")
        page = int(meta.get("page_number", 1)) if meta.get("page_number") is not None else 1
        chunk_index = int(meta.get("chunk_index", 0)) if meta.get("chunk_index") is not None else i

        cited_text = f"{text.strip()} [Source: {source}, p.{page}]"
        docs.append(cited_text)

        citations.append({
            "source": source,
            "page": page,
            "chunk_index": chunk_index,
            "relevance_score": relevance,
        })

    context = "\n\n".join(docs)
    return {"context": context, "citations": citations}

"""
rag/embedder.py
================
HuggingFace sentence-transformers embeddings for RAG pipeline.
Uses sentence-transformers/all-MiniLM-L6-v2 by default for a free public embedding model.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from langchain_community.embeddings import HuggingFaceEmbeddings
from loguru import logger

from config.settings import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def get_embedder() -> HuggingFaceEmbeddings:
    """
    Load and cache the HuggingFace embedding model.
    Uses a free sentence-transformers model by default for broad compatibility.
    """
    logger.info("Loading embedding model: {}", settings.embedding_model)
    embedder = HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": "cpu"},           # Change to "cuda" if GPU available
        encode_kwargs={
            "batch_size": 32,
        },
    )
    logger.info("Embedding model loaded successfully")
    return embedder


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of text strings."""
    embedder = get_embedder()
    return embedder.embed_documents(texts)


def embed_query(query: str) -> List[float]:
    """Embed a single query string."""
    embedder = get_embedder()
    return embedder.embed_query(query)
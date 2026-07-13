import json
import os
from unittest import mock

import pytest

from rag import pipeline, retriever


def _set_chroma_client_tmp(monkeypatch, tmp_path):
    """Attempt to set chromadb PersistentClient to use a tmp directory.

    This is best-effort; exact chromadb constructor may vary across versions.
    """
    try:
        import chromadb

        def _client_factory():
            return chromadb.PersistentClient(path=str(tmp_path / "chroma"))

        monkeypatch.setattr(retriever, "_CLIENT", _client_factory())
    except Exception:
        # best-effort; tests will still run but may use global client
        pass


def test_ingest_and_retrieve(tmp_path, monkeypatch):
    txt = tmp_path / "doc.txt"
    txt.write_text("Q3 revenue was $5.2M, up 12% year-over-year")

    _set_chroma_client_tmp(monkeypatch, tmp_path)

    res = pipeline.ingest_document(str(txt), doc_type="test")
    assert res.get("chunks_stored", 0) > 0

    out = pipeline.query_pipeline("What was Q3 revenue?")
    context = out.get("context", "")
    assert ("$5.2M" in context) or ("12%" in context)


def test_citation_format(tmp_path, monkeypatch):
    txt = tmp_path / "doc2.txt"
    txt.write_text("Q3 revenue was $5.2M, up 12% year-over-year")

    _set_chroma_client_tmp(monkeypatch, tmp_path)
    pipeline.ingest_document(str(txt), doc_type="test")

    out = retriever.retrieve("Q3 revenue")
    citations = out.get("citations", [])
    assert isinstance(citations, list) and len(citations) > 0
    for c in citations:
        assert "source" in c and "chunk_index" in c and "relevance_score" in c


def test_empty_collection_returns_empty_context(tmp_path, monkeypatch):
    # create a fresh client pointing to empty folder
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(tmp_path / "chroma_empty"))
        # patch module client
        monkeypatch.setattr(retriever, "_CLIENT", client)
    except Exception:
        # fallback: try to proceed without explicit client patch
        pass

    out = retriever.retrieve("anything")
    assert out.get("context", "") == ""
    assert out.get("citations", []) == []
"""
tests/test_rag.py
==================
Unit tests for the RAG pipeline components.
"""



from pathlib import Path

import pytest

from rag.chunker import chunk_documents
from langchain_core.documents import Document


class TestChunker:
    def test_basic_chunking(self):
        docs = [Document(page_content="Hello world. " * 100, metadata={"source": "test.txt"})]
        chunks = chunk_documents(docs, chunk_size=200, chunk_overlap=20)
        assert len(chunks) > 1

    def test_metadata_preserved(self):
        docs = [Document(page_content="Test content.", metadata={"source": "doc.pdf", "page": 1})]
        chunks = chunk_documents(docs)
        assert all(c.metadata.get("source") == "doc.pdf" for c in chunks)

    def test_chunk_index_added(self):
        docs = [Document(page_content="Word " * 200, metadata={})]
        chunks = chunk_documents(docs, chunk_size=100)
        assert all("chunk_index" in c.metadata for c in chunks)

    def test_empty_input(self):
        chunks = chunk_documents([])
        assert chunks == []
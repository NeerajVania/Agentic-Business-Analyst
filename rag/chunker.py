"""
rag/chunker.py
==============
Text chunking strategies for RAG ingestion.
"""

from __future__ import annotations

from typing import List

from langchain_core.documents import Document
from loguru import logger


def chunk_documents(
    documents: List[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> List[Document]:
    """
    Split documents into overlapping chunks for vector storage.

    Uses RecursiveCharacterTextSplitter which respects paragraph and
    sentence boundaries before character boundaries.

    Args:
        documents: Raw LangChain documents.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of chunked Document objects with preserved metadata.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks = splitter.split_documents(documents)

    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
        chunk.metadata["chunk_size"] = len(chunk.page_content)

    logger.info(
        "Chunked {} documents → {} chunks (size={}, overlap={})",
        len(documents), len(chunks), chunk_size, chunk_overlap,
    )
    return chunks

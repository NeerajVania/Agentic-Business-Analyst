"""
rag/loader.py
=============
Document loaders for the RAG pipeline.
Supports: PDF, DOCX, TXT, MD
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from langchain_core.documents import Document
from loguru import logger


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def load_document(file_path: str | Path) -> List[Document]:
    """
    Load a single document from disk.

    Args:
        file_path: Path to the document.

    Returns:
        List of LangChain Document objects.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported: {SUPPORTED_EXTENSIONS}"
        )

    logger.info("Loading document: {} ({})", path.name, ext)

    try:
        if ext == ".pdf":
            from langchain_community.document_loaders import PyPDFLoader
            loader = PyPDFLoader(str(path))
        elif ext == ".docx":
            from langchain_community.document_loaders import Docx2txtLoader
            loader = Docx2txtLoader(str(path))
        elif ext in {".txt", ".md"}:
            from langchain_community.document_loaders import TextLoader
            loader = TextLoader(str(path), encoding="utf-8")
        else:
            from langchain_community.document_loaders import UnstructuredFileLoader
            loader = UnstructuredFileLoader(str(path))

        docs = loader.load()

        for doc in docs:
            doc.metadata.setdefault("source", path.name)
            doc.metadata.setdefault("file_type", ext)

        logger.info("Loaded {} page(s)/chunk(s) from {}", len(docs), path.name)
        return docs

    except Exception as exc:
        logger.error("Failed to load {}: {}", path.name, exc)
        raise


def load_multiple_documents(file_paths: List[str | Path]) -> List[Document]:
    """Load and combine multiple documents."""
    all_docs: List[Document] = []
    for fp in file_paths:
        try:
            docs = load_document(fp)
            all_docs.extend(docs)
        except Exception as exc:
            logger.warning("Skipping {}: {}", fp, exc)
    logger.info("Total documents loaded: {}", len(all_docs))
    return all_docs

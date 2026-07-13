"""
vectorstore/chroma_store.py
============================
ChromaDB vector store client with HuggingFace BGE embeddings.
"""

from __future__ import annotations

from typing import List, Optional

from langchain_core.documents import Document
from loguru import logger

from rag.embedder import get_embedder
from config.settings import get_settings

settings = get_settings()


class ChromaStore:
    """
    Wrapper around LangChain's Chroma integration.
    Provides a clean API for add / search / delete operations.
    """

    def __init__(self, collection_name: Optional[str] = None):
        self.collection_name = collection_name or settings.chroma_collection
        self.embedder = get_embedder()
        self._store = self._init_store()

    def _init_store(self):
        """Initialise or connect to a ChromaDB collection."""
        from langchain_chroma import Chroma
        persist_dir = str(settings.vectorstore_dir / self.collection_name)

        logger.info(
            "Connecting to ChromaDB collection '{}' at {}",
            self.collection_name,
            persist_dir,
        )

        store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedder,
            persist_directory=persist_dir,
            collection_metadata={"hnsw:space": "cosine"},
        )
        return store

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to the vector store. Returns list of IDs."""
        if not documents:
            return []
        ids = self._store.add_documents(documents)
        logger.info(
            "Added {} documents to collection '{}'",
            len(documents),
            self.collection_name,
        )
        return ids

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Optional[dict] = None,
    ) -> List[Document]:
        """Retrieve top-k most similar documents."""
        try:
            results = self._store.similarity_search(
                query=query,
                k=k,
                filter=filter_metadata,
            )
            logger.info(
                "Retrieved {} results for query: '{}'",
                len(results),
                query[:50],
            )
            return results
        except Exception as exc:
            logger.error("ChromaDB search failed: {}", exc)
            return []

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 5,
    ) -> List[tuple[Document, float]]:
        """Retrieve top-k documents with similarity scores."""
        try:
            return self._store.similarity_search_with_score(query=query, k=k)
        except Exception as exc:
            logger.error("ChromaDB search with score failed: {}", exc)
            return []

    def delete_collection(self) -> None:
        """Delete the entire collection from ChromaDB."""
        self._store.delete_collection()
        logger.warning("Deleted collection '{}'", self.collection_name)

    def count(self) -> int:
        """Return the number of documents in the collection."""
        try:
            return self._store._collection.count()
        except Exception:
            return 0


# ── Convenience function ──────────────────────────────────────────────────────

def get_chroma_collection(collection_name: Optional[str] = None) -> ChromaStore:
    """Factory function to get a ChromaStore instance."""
    return ChromaStore(collection_name=collection_name)
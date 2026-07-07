"""
RAGService
==========
Thin facade over the project's real retrieval-augmented generation pipeline.

The actual chunking, embedding, and vector-search logic lives in the `rag/`
package (rag.ingestion.document_chunker, rag.embeddings.embedding_service,
rag.vector_store.vector_store_service) and is invoked end-to-end by
`SemanticRetrievalService`, which `DocumentRetrievalAgent` calls directly.

This module exists so other services or scripts can depend on a single,
stable `app.services.rag_service` import path without needing to know the
internal package layout of `rag/` or `SemanticRetrievalService`'s
database-session requirement.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.semantic_retrieval_service import SemanticRetrievalService


class RAGService:
    """Convenience wrapper exposing semantic document retrieval to callers
    that only need a simple search() entry point (e.g. ad-hoc scripts,
    notebooks, or future agents) without re-deriving SemanticRetrievalService's
    constructor requirements each time."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._semantic_retrieval = SemanticRetrievalService(db)

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        exclude_document_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Run semantic retrieval over the full document corpus and return the
        top_k most relevant evidence chunks, each with relevance scoring and
        traceable source metadata."""
        result = self._semantic_retrieval.search(
            query=query,
            top_k=top_k,
            exclude_document_ids=exclude_document_ids,
        )
        return list(result.get("semantic_evidence", []))

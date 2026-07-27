from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.services.document_metadata_service import DocumentMetadataService, build_source_uri


class UploadedDocumentSearchService:
    STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "about",
        "show",
        "tell",
        "what",
        "where",
        "when",
        "why",
        "how",
        "list",
        "find",
        "document",
        "documents",
        "file",
        "files",
        "evidence",
        "supporting",
        "uploaded",
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.metadata_service = DocumentMetadataService(db)

    def search(
        self,
        *,
        query: str,
        top_k: int = 5,
        attached_document_ids: set[str] | None = None,
        exclude_document_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        attached_document_ids = attached_document_ids or set()
        exclude_document_ids = exclude_document_ids or set()

        documents = self.metadata_service.list_documents(uploaded_only=True)
        scored: list[tuple[float, dict[str, Any]]] = []
        for document in documents:
            document_id = str(document.get("document_id") or "")
            if not document_id or document_id in exclude_document_ids:
                continue

            artifact = self._load_artifact(document)
            searchable_text = self._build_searchable_text(document, artifact)
            score = self._score(query, searchable_text)

            if document_id in attached_document_ids:
                score += 3.0

            if score <= 0 and document_id not in attached_document_ids:
                continue

            processing = artifact.get("processing", {}) if isinstance(artifact.get("processing"), dict) else {}
            content_snippet = str(processing.get("content_snippet") or "").strip()
            signals = processing.get("signals") if isinstance(processing.get("signals"), list) else []
            processing_summary = str(processing.get("processing_summary") or "").strip()

            scored.append(
                (
                    score,
                    {
                        **document,
                        "source_uri": document.get("source_uri") or build_source_uri(document),
                        "content_snippet": content_snippet or str(document.get("content_snippet") or ""),
                        "processing_summary": processing_summary,
                        "document_intelligence": processing.get("document_intelligence") or {},
                        "document_signals": [str(signal) for signal in signals if str(signal).strip()],
                        "relevance_score": round(min(score / 8.0, 1.0), 3),
                        "retrieval_mode": "uploaded_document_search",
                        "reason_selected": self._reason_selected(query=query, document=document, processing=processing),
                        "selection_explanation": {
                            "document_id": document_id,
                            "selection_reason": self._reason_selected(query=query, document=document, processing=processing),
                            "supports": self._supports_text(processing),
                            "relevance_summary": self._relevance_summary(query=query, document=document, processing=processing),
                            "confidence_note": "Grounded in uploaded document metadata and extracted content.",
                        },
                    },
                )
            )

        scored.sort(key=lambda item: (-item[0], str(item[1].get("document_id") or "")))
        return [document for _, document in scored[:top_k]]

    def _load_artifact(self, document: dict[str, Any]) -> dict[str, Any]:
        file_path = str(document.get("file_path") or "")
        if not file_path:
            return {}
        artifact_path = Path(file_path).with_suffix(f"{Path(file_path).suffix}.meta.json")
        if not artifact_path.exists() or not artifact_path.is_file():
            return {}
        try:
            return json.loads(artifact_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _build_searchable_text(self, document: dict[str, Any], artifact: dict[str, Any]) -> str:
        processing = artifact.get("processing", {}) if isinstance(artifact.get("processing"), dict) else {}
        fields = [
            document.get("document_id"),
            document.get("file_name"),
            document.get("document_type"),
            document.get("document_category"),
            document.get("source_metadata_file"),
            processing.get("processing_summary"),
            processing.get("content_snippet"),
            " ".join(str(signal) for signal in processing.get("signals", []) if signal),
            " ".join(str(item) for item in processing.get("risk_contribution", []) if item),
        ]
        return " ".join(str(value) for value in fields if value)

    def _score(self, query: str, searchable_text: str) -> float:
        query_tokens = [token for token in re.findall(r"[a-z0-9]+", query.lower()) if token not in self.STOPWORDS]
        if not query_tokens:
            return 0.0
        haystack = searchable_text.lower()
        score = 0.0
        for token in query_tokens:
            if token in haystack:
                score += 1.0
        if any(term in haystack for term in ("policy", "email", "report", "contract", "minutes", "sop")):
            score += 0.5
        return score

    def _reason_selected(
        self,
        *,
        query: str,
        document: dict[str, Any],
        processing: dict[str, Any],
    ) -> str:
        file_name = str(document.get("file_name") or "uploaded document")
        processing_summary = str(processing.get("processing_summary") or "").strip()
        if processing_summary:
            return f"{file_name} matched the query through its extracted content and processing summary."
        return f"{file_name} matched the query through uploaded document metadata and extracted snippet."

    def _supports_text(self, processing: dict[str, Any]) -> str:
        signals = processing.get("signals") if isinstance(processing.get("signals"), list) else []
        if signals:
            return "Signals detected: " + ", ".join(str(signal) for signal in signals[:4] if str(signal).strip())
        return "Supports the query through uploaded document content."

    def _relevance_summary(
        self,
        *,
        query: str,
        document: dict[str, Any],
        processing: dict[str, Any],
    ) -> str:
        query_label = query.strip()[:80] or "the investigation query"
        category = str(document.get("document_category") or document.get("document_type") or "document")
        return f"Uploaded {category} evidence is relevant to '{query_label}'."

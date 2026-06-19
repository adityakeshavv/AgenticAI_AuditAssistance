from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from app.services.document_metadata_service import DocumentMetadataService


LOOKUP_KEYS = (
    "vendor_id",
    "employee_id",
    "transaction_id",
    "contract_id",
    "investigation_id",
)


class DocumentRetrievalAgent:
    def __init__(self, db: Session) -> None:
        self.service = DocumentMetadataService(db)

    def retrieve(
        self,
        *,
        query: str,
        structured_intent: dict[str, Any],
        transaction_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        lookup_values = self._collect_lookup_values(structured_intent, transaction_results)
        documents: dict[str, dict[str, Any]] = {}

        for vendor_id in lookup_values["vendor_id"]:
            for document in self.service.get_documents_by_vendor_id(vendor_id):
                documents[document["document_id"]] = document

        for employee_id in lookup_values["employee_id"]:
            for document in self.service.get_documents_by_employee_id(employee_id):
                documents[document["document_id"]] = document

        for transaction_id in lookup_values["transaction_id"]:
            for document in self.service.get_documents_by_transaction_id(transaction_id):
                documents[document["document_id"]] = document

        for contract_id in lookup_values["contract_id"]:
            for document in self.service.get_documents_by_contract_id(contract_id):
                documents[document["document_id"]] = document

        for investigation_id in lookup_values["investigation_id"]:
            for document in self.service.get_documents_by_investigation_id(investigation_id):
                documents[document["document_id"]] = document

        document_list = list(documents.values())
        sources = self._build_sources(document_list)

        return {
            "agent": "document_retrieval_agent",
            "query": query,
            "lookup_values": lookup_values,
            "documents": document_list,
            "document_count": len(document_list),
            "sources": sources,
        }

    def _collect_lookup_values(
        self,
        structured_intent: dict[str, Any],
        transaction_results: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        lookup_values: dict[str, set[str]] = {key: set() for key in LOOKUP_KEYS}

        filters = structured_intent.get("filters") if isinstance(structured_intent.get("filters"), dict) else {}
        for key in LOOKUP_KEYS:
            value = filters.get(key)
            if isinstance(value, dict):
                value = value.get("value")
            if value not in (None, ""):
                lookup_values[key].add(str(value))

        for row in transaction_results:
            vendor_id = row.get("vendor_id")
            transaction_id = row.get("transaction_id")
            employee_id = row.get("employee_id")
            contract_id = row.get("contract_id")
            investigation_id = row.get("investigation_id")

            for key, value in (
                ("vendor_id", vendor_id),
                ("transaction_id", transaction_id),
                ("employee_id", employee_id),
                ("contract_id", contract_id),
                ("investigation_id", investigation_id),
            ):
                if value not in (None, ""):
                    lookup_values[key].add(str(value))

        return {key: sorted(values) for key, values in lookup_values.items()}

    def _build_sources(self, documents: Iterable[dict[str, Any]]) -> list[str]:
        sources: list[str] = []
        for document in documents:
            file_path = document.get("file_path")
            source_metadata_file = document.get("source_metadata_file")
            if file_path and file_path not in sources:
                sources.append(file_path)
            if source_metadata_file and source_metadata_file not in sources:
                sources.append(source_metadata_file)
        return sources

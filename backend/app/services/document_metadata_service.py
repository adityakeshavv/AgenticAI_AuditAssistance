from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud import document_metadata_crud
from app.models import DocumentMetadata


def serialize_document_metadata(document: DocumentMetadata) -> dict[str, Any]:
    return {
        "document_id": document.document_id,
        "document_type": document.document_type,
        "document_category": document.document_category,
        "related_vendor_id": document.related_vendor_id,
        "related_employee_id": document.related_employee_id,
        "related_transaction_id": document.related_transaction_id,
        "related_contract_id": document.related_contract_id,
        "related_investigation_id": document.related_investigation_id,
        "creation_date": document.creation_date.isoformat() if isinstance(document.creation_date, date) else document.creation_date,
        "file_name": document.file_name,
        "file_path": document.file_path,
        "source_uri": build_source_uri(
            {
                "document_id": document.document_id,
                "file_path": document.file_path,
                "file_name": document.file_name,
            }
        ),
        "source_metadata_file": document.source_metadata_file,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }


def build_citation_record(
    document: dict[str, Any],
    *,
    page_number: int | None = None,
    section_title: str | None = None,
    citation_text: str | None = None,
    anchor_text: str | None = None,
    start_offset: int | None = None,
    end_offset: int | None = None,
    chunk_id: str | None = None,
    relevance_score: float | None = None,
) -> dict[str, Any]:
    source_uri = document.get("source_uri")
    if not source_uri:
        source_uri = build_source_uri(document)
    return {
        "document_id": document.get("document_id"),
        "file_name": document.get("file_name"),
        "source_uri": source_uri,
        "page_number": page_number if page_number is not None else document.get("page_number"),
        "section_title": section_title if section_title is not None else document.get("section_title"),
        "anchor_text": anchor_text if anchor_text is not None else document.get("anchor_text"),
        "start_offset": start_offset if start_offset is not None else document.get("start_offset"),
        "end_offset": end_offset if end_offset is not None else document.get("end_offset"),
        "chunk_id": chunk_id if chunk_id is not None else document.get("chunk_id"),
        "citation_text": citation_text if citation_text is not None else document.get("citation_text"),
        "relevance_score": relevance_score if relevance_score is not None else document.get("relevance_score"),
    }


def build_source_uri(document: dict[str, Any]) -> str:
    settings = get_settings()
    base_uri = str(settings.document_source_uri_base or "").strip()
    file_path = document.get("file_path")
    document_id = document.get("document_id") or ""

    if base_uri:
        return f"{base_uri.rstrip('/')}/{document_id}"

    if file_path:
        try:
            return Path(str(file_path)).resolve().as_uri()
        except Exception:
            return str(file_path)

    return document_id


class DocumentMetadataService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_document_by_id(self, document_id: str) -> dict[str, Any] | None:
        document = document_metadata_crud.get_document_by_id(self.db, document_id)
        return serialize_document_metadata(document) if document else None

    def get_documents_by_vendor_id(self, vendor_id: str) -> list[dict[str, Any]]:
        return [serialize_document_metadata(document) for document in document_metadata_crud.get_documents_by_vendor_id(self.db, vendor_id)]

    def get_documents_by_employee_id(self, employee_id: str) -> list[dict[str, Any]]:
        return [serialize_document_metadata(document) for document in document_metadata_crud.get_documents_by_employee_id(self.db, employee_id)]

    def get_documents_by_transaction_id(self, transaction_id: str) -> list[dict[str, Any]]:
        return [
            serialize_document_metadata(document)
            for document in document_metadata_crud.get_documents_by_transaction_id(self.db, transaction_id)
        ]

    def get_documents_by_contract_id(self, contract_id: str) -> list[dict[str, Any]]:
        return [
            serialize_document_metadata(document)
            for document in document_metadata_crud.get_documents_by_contract_id(self.db, contract_id)
        ]

    def get_documents_by_investigation_id(self, investigation_id: str) -> list[dict[str, Any]]:
        return [
            serialize_document_metadata(document)
            for document in document_metadata_crud.get_documents_by_investigation_id(self.db, investigation_id)
        ]

    def get_documents_by_type(self, document_type: str) -> list[dict[str, Any]]:
        return [serialize_document_metadata(document) for document in document_metadata_crud.get_documents_by_type(self.db, document_type)]

    def list_documents(
        self,
        *,
        search: str | None = None,
        document_type: str | None = None,
        document_category: str | None = None,
        related_vendor_id: str | None = None,
        related_employee_id: str | None = None,
        related_transaction_id: str | None = None,
        related_contract_id: str | None = None,
        related_investigation_id: str | None = None,
        uploaded_only: bool = False,
    ) -> list[dict[str, Any]]:
        documents = document_metadata_crud.list_documents(
            self.db,
            search=search,
            document_type=document_type,
            document_category=document_category,
            related_vendor_id=related_vendor_id,
            related_employee_id=related_employee_id,
            related_transaction_id=related_transaction_id,
            related_contract_id=related_contract_id,
            related_investigation_id=related_investigation_id,
            uploaded_only=uploaded_only,
        )
        return [serialize_document_metadata(document) for document in documents]

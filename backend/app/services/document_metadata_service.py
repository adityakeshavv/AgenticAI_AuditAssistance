from datetime import date
from typing import Any

from sqlalchemy.orm import Session

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
        "source_metadata_file": document.source_metadata_file,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }


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

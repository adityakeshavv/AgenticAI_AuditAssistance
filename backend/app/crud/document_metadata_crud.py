from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import DocumentMetadata


def _base_document_metadata_query() -> Select[tuple[DocumentMetadata]]:
    return select(DocumentMetadata)


def get_document_by_id(db: Session, document_id: str) -> DocumentMetadata | None:
    return db.get(DocumentMetadata, document_id)


def get_documents_by_vendor_id(db: Session, vendor_id: str) -> list[DocumentMetadata]:
    stmt = _base_document_metadata_query().where(DocumentMetadata.related_vendor_id == vendor_id).order_by(
        DocumentMetadata.document_id
    )
    return list(db.scalars(stmt).all())


def get_documents_by_employee_id(db: Session, employee_id: str) -> list[DocumentMetadata]:
    stmt = _base_document_metadata_query().where(DocumentMetadata.related_employee_id == employee_id).order_by(
        DocumentMetadata.document_id
    )
    return list(db.scalars(stmt).all())


def get_documents_by_transaction_id(db: Session, transaction_id: str) -> list[DocumentMetadata]:
    stmt = _base_document_metadata_query().where(DocumentMetadata.related_transaction_id == transaction_id).order_by(
        DocumentMetadata.document_id
    )
    return list(db.scalars(stmt).all())


def get_documents_by_contract_id(db: Session, contract_id: str) -> list[DocumentMetadata]:
    stmt = _base_document_metadata_query().where(DocumentMetadata.related_contract_id == contract_id).order_by(
        DocumentMetadata.document_id
    )
    return list(db.scalars(stmt).all())


def get_documents_by_investigation_id(db: Session, investigation_id: str) -> list[DocumentMetadata]:
    stmt = _base_document_metadata_query().where(DocumentMetadata.related_investigation_id == investigation_id).order_by(
        DocumentMetadata.document_id
    )
    return list(db.scalars(stmt).all())


def get_documents_by_type(db: Session, document_type: str) -> list[DocumentMetadata]:
    stmt = _base_document_metadata_query().where(DocumentMetadata.document_type == document_type).order_by(
        DocumentMetadata.document_id
    )
    return list(db.scalars(stmt).all())

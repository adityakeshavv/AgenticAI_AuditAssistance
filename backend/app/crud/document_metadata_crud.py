from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.models import DocumentMetadata


def _base_document_metadata_query() -> Select[tuple[DocumentMetadata]]:
    return select(DocumentMetadata)


def list_documents(
    db: Session,
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
) -> list[DocumentMetadata]:
    conditions: list[Any] = []
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                DocumentMetadata.document_id.ilike(pattern),
                DocumentMetadata.file_name.ilike(pattern),
                DocumentMetadata.document_category.ilike(pattern),
                DocumentMetadata.document_type.ilike(pattern),
            )
        )
    if document_type:
        conditions.append(DocumentMetadata.document_type == document_type)
    if document_category:
        conditions.append(DocumentMetadata.document_category == document_category)
    if related_vendor_id:
        conditions.append(DocumentMetadata.related_vendor_id == related_vendor_id)
    if related_employee_id:
        conditions.append(DocumentMetadata.related_employee_id == related_employee_id)
    if related_transaction_id:
        conditions.append(DocumentMetadata.related_transaction_id == related_transaction_id)
    if related_contract_id:
        conditions.append(DocumentMetadata.related_contract_id == related_contract_id)
    if related_investigation_id:
        conditions.append(DocumentMetadata.related_investigation_id == related_investigation_id)
    if uploaded_only:
        conditions.append(DocumentMetadata.source_metadata_file.ilike("uploaded:%"))

    stmt = _base_document_metadata_query()
    if conditions:
        stmt = stmt.where(*conditions)
    stmt = stmt.order_by(DocumentMetadata.updated_at.desc(), DocumentMetadata.document_id.desc())
    return list(db.scalars(stmt).all())


def create_document_metadata(
    db: Session,
    *,
    document_id: str,
    document_type: str,
    document_category: str,
    creation_date: date,
    file_name: str,
    file_path: str,
    source_metadata_file: str,
    related_vendor_id: str | None = None,
    related_employee_id: str | None = None,
    related_transaction_id: str | None = None,
    related_contract_id: str | None = None,
    related_investigation_id: str | None = None,
) -> DocumentMetadata:
    now = datetime.now(timezone.utc)
    document = DocumentMetadata(
        document_id=document_id,
        document_type=document_type,
        document_category=document_category,
        related_vendor_id=related_vendor_id,
        related_employee_id=related_employee_id,
        related_transaction_id=related_transaction_id,
        related_contract_id=related_contract_id,
        related_investigation_id=related_investigation_id,
        creation_date=creation_date,
        file_name=file_name,
        file_path=file_path,
        source_metadata_file=source_metadata_file,
        created_at=now,
        updated_at=now,
    )
    db.add(document)
    db.flush()
    return document


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

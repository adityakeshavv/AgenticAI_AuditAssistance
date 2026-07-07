from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from app.crud.base import apply_pagination, count_statement
from app.models import ComplianceRecord


def _base_compliance_statement() -> Select[tuple[ComplianceRecord]]:
    return select(ComplianceRecord)


COMPARABLE_COLUMNS = {
    "assessment_date": ComplianceRecord.assessment_date,
    "expiry_date": ComplianceRecord.expiry_date,
}


def get_compliance_records_by_vendor_id(db: Session, vendor_id: str) -> list[ComplianceRecord]:
    stmt = (
        select(ComplianceRecord)
        .where(ComplianceRecord.vendor_id == vendor_id)
        .order_by(desc(ComplianceRecord.expiry_date))
    )
    return list(db.scalars(stmt).all())


def get_compliance_record_by_id(db: Session, compliance_id: str) -> ComplianceRecord | None:
    return db.get(ComplianceRecord, compliance_id)


def get_compliance_records_by_status(
    db: Session,
    status: str,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ComplianceRecord], int]:
    stmt = (
        _base_compliance_statement()
        .where(ComplianceRecord.status == status)
        .order_by(desc(ComplianceRecord.expiry_date))
    )
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total


def get_compliance_records_by_framework(
    db: Session,
    framework: str,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ComplianceRecord], int]:
    stmt = (
        _base_compliance_statement()
        .where(ComplianceRecord.framework == framework)
        .order_by(desc(ComplianceRecord.expiry_date))
    )
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total


def get_expired_compliance_records(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ComplianceRecord], int]:
    stmt = (
        _base_compliance_statement()
        .where(ComplianceRecord.status == "EXPIRED")
        .order_by(desc(ComplianceRecord.expiry_date))
    )
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total


def get_non_compliant_records(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ComplianceRecord], int]:
    stmt = (
        _base_compliance_statement()
        .where(ComplianceRecord.status == "NON_COMPLIANT")
        .order_by(desc(ComplianceRecord.expiry_date))
    )
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total


def get_compliance_records_filtered(
    db: Session,
    *,
    filters: dict[str, dict[str, object]] | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ComplianceRecord], int]:
    """Generic comparison-filter query, mirroring the transaction_crud pattern."""
    stmt = _base_compliance_statement()
    filters = filters or {}

    for field_name, condition in filters.items():
        column = COMPARABLE_COLUMNS.get(field_name)
        if column is None:
            continue
        operator = str(condition.get("operator", "")).strip()
        value = condition.get("value")
        if value is None:
            continue
        try:
            comparable_value = Decimal(str(value)) if field_name not in ("assessment_date", "expiry_date") else value
        except Exception:
            comparable_value = value

        if operator == ">":
            stmt = stmt.where(column > comparable_value)
        elif operator == ">=":
            stmt = stmt.where(column >= comparable_value)
        elif operator == "<":
            stmt = stmt.where(column < comparable_value)
        elif operator == "<=":
            stmt = stmt.where(column <= comparable_value)

    stmt = stmt.order_by(desc(ComplianceRecord.expiry_date))
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total

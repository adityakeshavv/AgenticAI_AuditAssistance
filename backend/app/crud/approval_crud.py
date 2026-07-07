from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from app.crud.base import apply_pagination, count_statement
from app.models import ApprovalWorkflow


def _base_approval_statement() -> Select[tuple[ApprovalWorkflow]]:
    return select(ApprovalWorkflow)


COMPARABLE_COLUMNS = {
    "transaction_amount": ApprovalWorkflow.transaction_amount,
    "approval_limit": ApprovalWorkflow.approval_limit,
    "approval_level": ApprovalWorkflow.approval_level,
}


def get_approval_by_id(db: Session, approval_id: str) -> ApprovalWorkflow | None:
    return db.get(ApprovalWorkflow, approval_id)


def get_approvals_by_transaction_id(db: Session, transaction_id: str) -> list[ApprovalWorkflow]:
    stmt = (
        select(ApprovalWorkflow)
        .where(ApprovalWorkflow.transaction_id == transaction_id)
        .order_by(desc(ApprovalWorkflow.approval_date), desc(ApprovalWorkflow.approval_level))
    )
    return list(db.scalars(stmt).all())


def get_approvals_by_approver_id(db: Session, approver_employee_id: str) -> list[ApprovalWorkflow]:
    stmt = (
        select(ApprovalWorkflow)
        .where(ApprovalWorkflow.approver_employee_id == approver_employee_id)
        .order_by(desc(ApprovalWorkflow.approval_date))
    )
    return list(db.scalars(stmt).all())


def get_approvals_by_status(
    db: Session,
    status: str,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ApprovalWorkflow], int]:
    stmt = (
        _base_approval_statement()
        .where(ApprovalWorkflow.approval_status == status)
        .order_by(desc(ApprovalWorkflow.approval_date))
    )
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total


def get_exceeded_authority_approvals(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ApprovalWorkflow], int]:
    """Approvals where the transaction amount exceeded the approver's authorized limit."""
    stmt = (
        _base_approval_statement()
        .where(ApprovalWorkflow.transaction_amount > ApprovalWorkflow.approval_limit)
        .order_by(desc(ApprovalWorkflow.approval_date), desc(ApprovalWorkflow.transaction_amount))
    )
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total


def get_escalated_approvals(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ApprovalWorkflow], int]:
    stmt = (
        _base_approval_statement()
        .where(ApprovalWorkflow.approval_status == "ESCALATED")
        .order_by(desc(ApprovalWorkflow.approval_date))
    )
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total


def get_rejected_approvals(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ApprovalWorkflow], int]:
    stmt = (
        _base_approval_statement()
        .where(ApprovalWorkflow.approval_status == "REJECTED")
        .order_by(desc(ApprovalWorkflow.approval_date))
    )
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total


def get_approvals_filtered(
    db: Session,
    *,
    filters: dict[str, dict[str, object]] | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ApprovalWorkflow], int]:
    """Generic comparison-filter query, mirroring the transaction_crud pattern."""
    stmt = _base_approval_statement()
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
            comparable_value = Decimal(str(value))
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

    stmt = stmt.order_by(desc(ApprovalWorkflow.approval_date))
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from app.crud.base import apply_pagination, count_statement
from app.models import ExpenseClaim


def _base_expense_statement() -> Select[tuple[ExpenseClaim]]:
    return select(ExpenseClaim)


COMPARABLE_COLUMNS = {
    "amount": ExpenseClaim.amount,
}


def get_expense_claim_by_id(db: Session, claim_id: str) -> ExpenseClaim | None:
    return db.get(ExpenseClaim, claim_id)


def get_expense_claims_by_employee_id(db: Session, employee_id: str) -> list[ExpenseClaim]:
    stmt = (
        select(ExpenseClaim)
        .where(ExpenseClaim.employee_id == employee_id)
        .order_by(desc(ExpenseClaim.claim_date))
    )
    return list(db.scalars(stmt).all())


def get_flagged_expense_claims(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ExpenseClaim], int]:
    stmt = (
        _base_expense_statement()
        .where(ExpenseClaim.approval_status == "FLAGGED")
        .order_by(desc(ExpenseClaim.claim_date))
    )
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total


def get_expense_claims_without_receipt(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ExpenseClaim], int]:
    stmt = (
        _base_expense_statement()
        .where(ExpenseClaim.receipt_attached.is_(False))
        .order_by(desc(ExpenseClaim.claim_date))
    )
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total


def get_expense_claims_by_category(
    db: Session,
    category: str,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ExpenseClaim], int]:
    stmt = (
        _base_expense_statement()
        .where(ExpenseClaim.expense_category == category)
        .order_by(desc(ExpenseClaim.claim_date))
    )
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total


def get_expense_claims_filtered(
    db: Session,
    *,
    filters: dict[str, dict[str, object]] | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ExpenseClaim], int]:
    stmt = _base_expense_statement()
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

    stmt = stmt.order_by(desc(ExpenseClaim.claim_date))
    total = count_statement(db, stmt)
    rows = list(db.scalars(apply_pagination(stmt, page, page_size)).all())
    return rows, total

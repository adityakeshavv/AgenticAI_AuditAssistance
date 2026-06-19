import re
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, desc, or_, select
from sqlalchemy.orm import Session

from app.crud.base import apply_pagination, count_statement
from app.models import TransactionMaster


def _base_transaction_statement() -> Select[tuple[TransactionMaster]]:
    return select(TransactionMaster)


def classify_transaction_intent(query: str) -> str | None:
    normalized_query = query.lower().strip()

    if not normalized_query:
        return None

    if re.search(r"\brecent\b.*\bflagged\b|\bflagged\b.*\brecent\b", normalized_query):
        return "recent_flagged_transactions"

    if re.search(r"\bflagged\b", normalized_query):
        return "flagged_transactions"

    if re.search(r"\bhigh[- ]risk\b", normalized_query):
        return "high_risk_transactions"

    if re.search(r"\b(?:above|greater than|over)\s+[0-9][0-9,]*(?:\.[0-9]+)?\b", normalized_query):
        return "transactions_above_amount"

    if re.search(r"\bsuspicious\b|\bfraud\b", normalized_query):
        return "suspicious_transactions"

    return None


def _extract_amount(query: str) -> Decimal | None:
    match = re.search(r"(?:above|greater than|over)\s+([0-9][0-9,]*(?:\.[0-9]+)?)", query)
    if not match:
        return None
    return Decimal(match.group(1).replace(",", ""))


SUPPORTED_INTENT_ALIASES = {
    "transactions_filtered": "transactions_filtered",
    "transactions_by_amount": "transactions_filtered",
    "transactions_by_risk": "transactions_filtered",
    "flagged_transactions": "flagged_transactions",
    "recent_flagged_transactions": "recent_flagged_transactions",
}

COMPARABLE_COLUMNS = {
    "amount": TransactionMaster.amount,
    "risk_score": TransactionMaster.risk_score,
}


def build_transaction_statement(
    structured_intent: dict[str, Any],
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[Select[tuple[TransactionMaster]], str]:
    intent = _normalize_intent(structured_intent.get("intent"))
    filters = structured_intent.get("filters") if isinstance(structured_intent.get("filters"), dict) else {}

    if intent is None:
        raise ValueError("unsupported_query")

    if intent == "recent_flagged_transactions":
        statement = (
            _base_transaction_statement()
            .where(TransactionMaster.status == "FLAGGED")
            .order_by(desc(TransactionMaster.transaction_date))
        )
    elif intent == "flagged_transactions":
        statement = (
            _base_transaction_statement()
            .where(TransactionMaster.status == "FLAGGED")
            .order_by(desc(TransactionMaster.transaction_date), desc(TransactionMaster.risk_score))
        )
    elif intent == "transactions_filtered":
        if not filters:
            raise ValueError("unsupported_intent")

        statement = _base_transaction_statement()
        order_clause = None

        for field, filter_spec in filters.items():
            column = COMPARABLE_COLUMNS.get(field)
            if column is None or not isinstance(filter_spec, dict):
                raise ValueError("unsupported_intent")

            operator = str(filter_spec.get("operator", "")).strip()
            value = _extract_decimal(filter_spec.get("value"))
            if operator not in {">", ">=", "<", "<="} or value is None:
                raise ValueError("unsupported_intent")

            if operator == ">":
                statement = statement.where(column > value)
                order_clause = column.desc()
            elif operator == ">=":
                statement = statement.where(column >= value)
                order_clause = column.desc()
            elif operator == "<":
                statement = statement.where(column < value)
                order_clause = column.asc()
            else:
                statement = statement.where(column <= value)
                order_clause = column.asc()

        if order_clause is not None:
            statement = statement.order_by(order_clause)
    else:
        raise ValueError("unsupported_intent")
    return apply_pagination(statement, page, page_size), intent


def _normalize_intent(intent: Any) -> str | None:
    if not isinstance(intent, str):
        return None
    return SUPPORTED_INTENT_ALIASES.get(intent)


def _extract_decimal(value: Any) -> Decimal | None:
    try:
        if value is None:
            return None
        return Decimal(str(value))
    except Exception:
        return None


def list_transactions(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[TransactionMaster], int]:
    statement = _base_transaction_statement().order_by(desc(TransactionMaster.transaction_date))
    total = count_statement(db, statement)
    rows = db.scalars(apply_pagination(statement, page, page_size)).all()
    return list(rows), total


def get_flagged_transactions(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[TransactionMaster], int]:
    statement = (
        _base_transaction_statement()
        .where(TransactionMaster.status == "FLAGGED")
        .order_by(desc(TransactionMaster.transaction_date), desc(TransactionMaster.risk_score))
    )
    total = count_statement(db, statement)
    rows = db.scalars(apply_pagination(statement, page, page_size)).all()
    return list(rows), total


def get_high_risk_transactions(
    db: Session,
    *,
    min_risk_score: Decimal = Decimal("0.800"),
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[TransactionMaster], int]:
    statement = (
        _base_transaction_statement()
        .where(TransactionMaster.risk_score >= min_risk_score)
        .order_by(desc(TransactionMaster.risk_score), desc(TransactionMaster.amount))
    )
    total = count_statement(db, statement)
    rows = db.scalars(apply_pagination(statement, page, page_size)).all()
    return list(rows), total


def get_suspicious_transactions(
    db: Session,
    *,
    min_risk_score: Decimal = Decimal("0.800"),
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[TransactionMaster], int]:
    statement = (
        _base_transaction_statement()
        .where(
            or_(
                TransactionMaster.status == "FLAGGED",
                TransactionMaster.risk_score >= min_risk_score,
            )
        )
        .order_by(desc(TransactionMaster.risk_score), desc(TransactionMaster.amount))
    )
    total = count_statement(db, statement)
    rows = db.scalars(apply_pagination(statement, page, page_size)).all()
    return list(rows), total


def get_transactions_above_amount(
    db: Session,
    *,
    min_amount: Decimal,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[TransactionMaster], int]:
    statement = (
        _base_transaction_statement()
        .where(TransactionMaster.amount > min_amount)
        .order_by(desc(TransactionMaster.amount))
    )
    total = count_statement(db, statement)
    rows = db.scalars(apply_pagination(statement, page, page_size)).all()
    return list(rows), total

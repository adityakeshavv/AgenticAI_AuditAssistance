from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.crud import expense_crud
from app.models import ExpenseClaim
from app.services.llm_router_service import StructuredIntentService

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10

EXPENSE_ALLOWED_INTENTS = [
    "expenses_filtered",
    "flagged_expenses",
    "expenses_without_receipt",
    "expenses_by_category",
]


def serialize_expense_claim(claim: ExpenseClaim) -> dict[str, Any]:
    return {
        "claim_id": claim.claim_id,
        "employee_id": claim.employee_id,
        "amount": float(claim.amount) if isinstance(claim.amount, Decimal) else claim.amount,
        "expense_category": claim.expense_category,
        "claim_date": claim.claim_date.isoformat() if isinstance(claim.claim_date, date) else claim.claim_date,
        "submission_date": claim.submission_date.isoformat() if isinstance(claim.submission_date, date) else claim.submission_date,
        "receipt_attached": claim.receipt_attached,
        "policy_id": claim.policy_id,
        "approval_status": claim.approval_status,
        "approved_by": claim.approved_by,
        "created_at": claim.created_at.isoformat() if isinstance(claim.created_at, datetime) else claim.created_at,
        "updated_at": claim.updated_at.isoformat() if isinstance(claim.updated_at, datetime) else claim.updated_at,
        "source_type": "expense_claim",
    }


def execute_expense_query(
    db: Session,
    query: str,
    *,
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    intent_service = StructuredIntentService()
    structured_intent = intent_service.extract(
        query,
        domain="expense",
        entity="expense_claim",
        allowed_intents=EXPENSE_ALLOWED_INTENTS,
    )

    if not structured_intent.get("supported"):
        return {
            "success": False,
            "reason": "unsupported_query",
            "message": "This query does not appear to be related to the expense claim domain.",
            "user_query": query,
            "structured_intent": structured_intent,
            "results": [],
        }

    intent = structured_intent.get("intent")
    filters = structured_intent.get("filters") if isinstance(structured_intent.get("filters"), dict) else {}

    if intent == "flagged_expenses":
        rows, total = expense_crud.get_flagged_expense_claims(db, page=page, page_size=page_size)
    elif intent == "expenses_without_receipt":
        rows, total = expense_crud.get_expense_claims_without_receipt(db, page=page, page_size=page_size)
    elif intent == "expenses_by_category":
        category = str((filters.get("expense_category") or {}).get("value") or "").strip()
        if not category:
            return {
                "success": False,
                "reason": "missing_category",
                "message": "An expense category could not be identified in the query.",
                "user_query": query,
                "structured_intent": structured_intent,
                "results": [],
            }
        rows, total = expense_crud.get_expense_claims_by_category(db, category, page=page, page_size=page_size)
    elif intent == "expenses_filtered":
        rows, total = expense_crud.get_expense_claims_filtered(db, filters=filters, page=page, page_size=page_size)
    else:
        return {
            "success": False,
            "reason": "unsupported_query",
            "message": "This query does not appear to be related to the expense claim domain.",
            "user_query": query,
            "structured_intent": structured_intent,
            "results": [],
        }

    results = [serialize_expense_claim(claim) for claim in rows]
    return {
        "success": True,
        "agent": "expense_agent",
        "intent": intent,
        "structured_intent": structured_intent,
        "original_query": structured_intent.get("original_query", query),
        "normalized_query": structured_intent.get("normalized_query"),
        "user_query": query,
        "result_count": len(results),
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "results": results,
        "outcome": "valid_query_with_no_results" if not results else "success",
        "message": "No matching expense claims were found." if not results else None,
    }


class ExpenseService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_claims_by_employee(self, employee_id: str) -> list[dict[str, Any]]:
        return [serialize_expense_claim(c) for c in expense_crud.get_expense_claims_by_employee_id(self.db, employee_id)]

    def get_claim_by_id(self, claim_id: str) -> dict[str, Any] | None:
        claim = expense_crud.get_expense_claim_by_id(self.db, claim_id)
        return serialize_expense_claim(claim) if claim else None

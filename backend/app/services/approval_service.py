from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.crud import approval_crud
from app.models import ApprovalWorkflow
from app.services.llm_router_service import StructuredIntentService

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10

APPROVAL_ALLOWED_INTENTS = [
    "approvals_filtered",
    "exceeded_authority_approvals",
    "escalated_approvals",
    "rejected_approvals",
]


def serialize_approval(approval: ApprovalWorkflow) -> dict[str, Any]:
    transaction_amount = float(approval.transaction_amount) if isinstance(approval.transaction_amount, Decimal) else approval.transaction_amount
    approval_limit = float(approval.approval_limit) if isinstance(approval.approval_limit, Decimal) else approval.approval_limit
    exceeded = bool(transaction_amount is not None and approval_limit is not None and transaction_amount > approval_limit)
    return {
        "approval_id": approval.approval_id,
        "transaction_id": approval.transaction_id,
        "transaction_amount": transaction_amount,
        "approver_employee_id": approval.approver_employee_id,
        "approval_level": approval.approval_level,
        "approval_limit": approval_limit,
        "approval_status": approval.approval_status,
        "approval_date": approval.approval_date.isoformat() if isinstance(approval.approval_date, date) else approval.approval_date,
        "rejection_reason": approval.rejection_reason,
        "delegation_ref": approval.delegation_ref,
        "exceeded_authority": exceeded,
        "created_at": approval.created_at.isoformat() if isinstance(approval.created_at, datetime) else approval.created_at,
        "updated_at": approval.updated_at.isoformat() if isinstance(approval.updated_at, datetime) else approval.updated_at,
        "source_type": "approval_workflow",
    }


def execute_approval_query(
    db: Session,
    query: str,
    *,
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    intent_service = StructuredIntentService()
    structured_intent = intent_service.extract(
        query,
        domain="approval",
        entity="approval_workflow",
        allowed_intents=APPROVAL_ALLOWED_INTENTS,
    )

    if not structured_intent.get("supported"):
        return {
            "success": False,
            "reason": "unsupported_query",
            "message": "This query does not appear to be related to the approval workflow domain.",
            "user_query": query,
            "structured_intent": structured_intent,
            "results": [],
        }

    intent = structured_intent.get("intent")
    filters = structured_intent.get("filters") if isinstance(structured_intent.get("filters"), dict) else {}

    if intent == "exceeded_authority_approvals":
        rows, total = approval_crud.get_exceeded_authority_approvals(db, page=page, page_size=page_size)
    elif intent == "escalated_approvals":
        rows, total = approval_crud.get_escalated_approvals(db, page=page, page_size=page_size)
    elif intent == "rejected_approvals":
        rows, total = approval_crud.get_rejected_approvals(db, page=page, page_size=page_size)
    elif intent == "approvals_filtered":
        rows, total = approval_crud.get_approvals_filtered(db, filters=filters, page=page, page_size=page_size)
    else:
        return {
            "success": False,
            "reason": "unsupported_query",
            "message": "This query does not appear to be related to the approval workflow domain.",
            "user_query": query,
            "structured_intent": structured_intent,
            "results": [],
        }

    results = [serialize_approval(approval) for approval in rows]
    return {
        "success": True,
        "agent": "approval_agent",
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
        "message": "No matching approval records were found." if not results else None,
    }


class ApprovalService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_approvals_by_transaction(self, transaction_id: str) -> list[dict[str, Any]]:
        return [serialize_approval(a) for a in approval_crud.get_approvals_by_transaction_id(self.db, transaction_id)]

    def get_approval_by_id(self, approval_id: str) -> dict[str, Any] | None:
        approval = approval_crud.get_approval_by_id(self.db, approval_id)
        return serialize_approval(approval) if approval else None

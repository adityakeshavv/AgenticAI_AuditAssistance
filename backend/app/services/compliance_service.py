from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.crud import compliance_crud
from app.models import ComplianceRecord
from app.services.llm_router_service import StructuredIntentService

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10

COMPLIANCE_ALLOWED_INTENTS = [
    "compliance_filtered",
    "expired_compliance",
    "non_compliant_records",
    "compliance_by_framework",
]


def serialize_compliance_record(record: ComplianceRecord) -> dict[str, Any]:
    return {
        "compliance_id": record.compliance_id,
        "vendor_id": record.vendor_id,
        "framework": record.framework,
        "status": record.status,
        "assessment_date": record.assessment_date.isoformat() if isinstance(record.assessment_date, date) else record.assessment_date,
        "expiry_date": record.expiry_date.isoformat() if isinstance(record.expiry_date, date) else record.expiry_date,
        "assessed_by": record.assessed_by,
        "findings_summary": record.findings_summary,
        "document_ref": record.document_ref,
        "created_at": record.created_at.isoformat() if isinstance(record.created_at, datetime) else record.created_at,
        "updated_at": record.updated_at.isoformat() if isinstance(record.updated_at, datetime) else record.updated_at,
        "source_type": "compliance_record",
    }


def execute_compliance_query(
    db: Session,
    query: str,
    *,
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    intent_service = StructuredIntentService()
    structured_intent = intent_service.extract(
        query,
        domain="compliance",
        entity="compliance_record",
        allowed_intents=COMPLIANCE_ALLOWED_INTENTS,
    )

    if not structured_intent.get("supported"):
        return {
            "success": False,
            "reason": "unsupported_query",
            "message": "This query does not appear to be related to the compliance domain.",
            "user_query": query,
            "structured_intent": structured_intent,
            "results": [],
        }

    intent = structured_intent.get("intent")
    filters = structured_intent.get("filters") if isinstance(structured_intent.get("filters"), dict) else {}

    if intent == "expired_compliance":
        rows, total = compliance_crud.get_expired_compliance_records(db, page=page, page_size=page_size)
    elif intent == "non_compliant_records":
        rows, total = compliance_crud.get_non_compliant_records(db, page=page, page_size=page_size)
    elif intent == "compliance_by_framework":
        framework = str((filters.get("framework") or {}).get("value") or "").strip()
        if not framework:
            return {
                "success": False,
                "reason": "missing_framework",
                "message": "A compliance framework could not be identified in the query.",
                "user_query": query,
                "structured_intent": structured_intent,
                "results": [],
            }
        rows, total = compliance_crud.get_compliance_records_by_framework(db, framework, page=page, page_size=page_size)
    elif intent == "compliance_filtered":
        rows, total = compliance_crud.get_compliance_records_filtered(db, filters=filters, page=page, page_size=page_size)
    else:
        return {
            "success": False,
            "reason": "unsupported_query",
            "message": "This query does not appear to be related to the compliance domain.",
            "user_query": query,
            "structured_intent": structured_intent,
            "results": [],
        }

    results = [serialize_compliance_record(record) for record in rows]
    return {
        "success": True,
        "agent": "compliance_agent",
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
        "message": "No matching compliance records were found." if not results else None,
    }


class ComplianceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_records_by_vendor(self, vendor_id: str) -> list[dict[str, Any]]:
        return [serialize_compliance_record(r) for r in compliance_crud.get_compliance_records_by_vendor_id(self.db, vendor_id)]

    def get_record_by_id(self, compliance_id: str) -> dict[str, Any] | None:
        record = compliance_crud.get_compliance_record_by_id(self.db, compliance_id)
        return serialize_compliance_record(record) if record else None

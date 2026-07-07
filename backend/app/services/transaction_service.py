from typing import Any

from sqlalchemy import Select
from sqlalchemy.orm import Session

from app.crud import transaction_crud
from app.models import TransactionMaster
from app.services.llm_router_service import StructuredIntentService


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10
TRANSACTION_ALLOWED_INTENTS = [
    "transactions_filtered",
    "flagged_transactions",
    "recent_flagged_transactions",
]


def execute_transaction_query(
    db: Session,
    query: str,
    *,
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
    trace_context: Any | None = None,
) -> dict[str, Any]:
    intent_service = StructuredIntentService()
    structured_intent = intent_service.extract(
        query,
        domain="transaction",
        entity="transaction",
        allowed_intents=TRANSACTION_ALLOWED_INTENTS,
        trace_context=trace_context,
    )

    if not structured_intent.get("supported"):
        return {
            "success": False,
            "reason": "unsupported_query",
            "message": "This query does not appear to be related to the audit domains currently supported.",
            "user_query": query,
            "structured_intent": structured_intent,
            "validation": {
                "passed": False,
                "checks": [
                    {
                        "name": "query_matches_supported_domain",
                        "status": "failed",
                    }
                ],
            },
            "trace": [
                {
                    "step": "intent_extraction",
                    "structured_intent": structured_intent,
                    "status": "rejected",
                }
            ],
        }

    try:
        statement, intent = transaction_crud.build_transaction_statement(
            structured_intent,
            page=page,
            page_size=page_size,
        )
    except ValueError:
        return {
            "success": False,
            "reason": "unsupported_query",
            "message": "This query does not appear to be related to the audit domains currently supported.",
            "user_query": query,
            "structured_intent": structured_intent,
            "validation": {
                "passed": False,
                "checks": [
                    {
                        "name": "query_matches_intent",
                        "status": "failed",
                    }
                ],
            },
            "trace": [
                {
                    "step": "intent_extraction",
                    "structured_intent": structured_intent,
                    "status": "rejected",
                }
            ],
        }

    sql_span = trace_context.begin_span(
        "transaction_sql_execution",
        input_payload={
            "structured_intent": structured_intent,
            "intent": intent,
            "page": page,
            "page_size": page_size,
        },
        metadata={"service": "transaction_service"},
    ) if trace_context else None

    generated_sql = compile_sql(statement, db)
    transactions = db.scalars(statement).all()
    result_count = len(transactions)
    results = [serialize_transaction(transaction) for transaction in transactions]
    validation = build_transaction_validation(
        structured_intent=structured_intent,
        intent=intent,
        generated_sql=generated_sql,
        results=results,
    )
    if sql_span:
        sql_span.finish(
            output={
                "generated_sql": generated_sql,
                "result_count": result_count,
                "validation": validation,
            },
            metadata={
                "generated_sql": generated_sql,
                "result_count": result_count,
                "validation_passed": validation.get("passed"),
            },
        )

    return {
        "success": True,
        "agent": "transaction_agent",
        "intent": intent,
        "structured_intent": structured_intent,
        "original_query": structured_intent.get("original_query", query),
        "normalized_query": structured_intent.get("normalized_query"),
        "user_query": query,
        "generated_sql": generated_sql,
        "result_count": result_count,
        "page": page,
        "page_size": page_size,
        "results": results,
        "validation": validation,
        "outcome": "valid_query_with_no_results" if result_count == 0 else "success",
        "message": "No matching transaction records were found." if result_count == 0 else None,
        "trace": [
            {
                "step": "intent_extraction",
                "selected_agent": "transaction_agent",
                "structured_intent": structured_intent,
            },
            {
                "step": "sql_generation",
            },
            {
                "step": "database_execution",
                "rows_returned": result_count,
            },
        ],
    }


def compile_sql(statement: Select[Any], db: Session) -> str:
    bind = db.get_bind()
    dialect = bind.dialect if bind is not None else None
    compiled = statement.compile(
        dialect=dialect,
        compile_kwargs={"literal_binds": True},
    )
    return str(compiled)


def build_transaction_validation(
    *,
    structured_intent: dict[str, Any],
    intent: str,
    generated_sql: str,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    query_matches_supported_domain = bool(structured_intent.get("supported")) and structured_intent.get("domain") == "transaction"
    checks.append(
        {
            "name": "query_matches_supported_domain",
            "status": "passed" if query_matches_supported_domain else "failed",
        }
    )

    query_matches_intent = validate_query_matches_intent(structured_intent, intent)
    checks.append(
        {
            "name": "query_matches_intent",
            "status": "passed" if query_matches_intent else "failed",
        }
    )

    sql_supports_query = validate_sql_matches_intent(generated_sql, intent, structured_intent.get("filters", {}))
    checks.append(
        {
            "name": "sql_supports_query",
            "status": "passed" if sql_supports_query else "failed",
        }
    )

    generated_sql_present = bool(generated_sql.strip())
    checks.append(
        {
            "name": "generated_sql_present",
            "status": "passed" if generated_sql_present else "failed",
        }
    )

    sql_result_present = results is not None
    checks.append(
        {
            "name": "sql_result_present",
            "status": "passed" if sql_result_present else "failed",
        }
    )

    result_count_non_zero = len(results) > 0
    checks.append(
        {
            "name": "result_count_non_zero",
            "status": "passed" if result_count_non_zero else "skipped",
        }
    )

    finding_supported = validate_results_against_intent(intent, results, structured_intent.get("filters", {}))
    checks.append(
        {
            "name": "finding_supported_by_results",
            "status": "passed" if finding_supported else "skipped",
        }
    )

    return {
        "passed": not any(check["status"] == "failed" for check in checks),
        "checks": checks,
    }


def validate_query_matches_intent(structured_intent: dict[str, Any], intent: str) -> bool:
    extracted_intent = structured_intent.get("intent")
    if not structured_intent.get("supported") or extracted_intent != intent:
        return False
    if intent == "transactions_filtered":
        filters = structured_intent.get("filters", {})
        return isinstance(filters, dict) and bool(filters)
    return True


def validate_sql_matches_intent(generated_sql: str, intent: str, filters: dict[str, Any]) -> bool:
    normalized_sql = generated_sql.lower()

    if intent in {"flagged_transactions", "recent_flagged_transactions"}:
        return "status = 'flagged'" in normalized_sql

    if intent == "transactions_filtered":
        return isinstance(filters, dict) and bool(filters) and all(
            _sql_clause_present(normalized_sql, field, spec) for field, spec in filters.items()
        )

    return False


def validate_results_against_intent(
    intent: str,
    results: list[dict[str, Any]],
    filters: dict[str, Any],
) -> bool:
    if not results:
        return False

    if intent in {"flagged_transactions", "recent_flagged_transactions"}:
        return all(str(result.get("status", "")).upper() == "FLAGGED" for result in results)

    if intent == "transactions_filtered":
        return isinstance(filters, dict) and bool(filters) and all(
            _result_matches_filter(result, field, spec)
            for result in results
            for field, spec in filters.items()
        )

    return True


def _is_high_risk(result: dict[str, Any]) -> bool:
    risk_score = result.get("risk_score")
    try:
        return risk_score is not None and float(risk_score) >= 0.8
    except (TypeError, ValueError):
        return False


def _sql_clause_present(normalized_sql: str, field: str, spec: dict[str, Any]) -> bool:
    if not isinstance(spec, dict):
        return False
    operator = str(spec.get("operator", "")).strip()
    if field not in {"amount", "risk_score"}:
        return False
    if operator not in {">", ">=", "<", "<="}:
        return False
    value = spec.get("value")
    if value is None:
        return False
    return f"{field} {operator}" in normalized_sql


def _result_matches_filter(result: dict[str, Any], field: str, spec: dict[str, Any]) -> bool:
    if not isinstance(spec, dict):
        return False
    operator = str(spec.get("operator", "")).strip()
    if field not in {"amount", "risk_score"}:
        return False
    if operator not in {">", ">=", "<", "<="}:
        return False
    threshold = spec.get("value")
    if threshold is None:
        return False
    value = result.get(field)
    try:
        if value is None:
            return False
        amount_value = float(value)
        threshold_value = float(threshold)
        if operator == ">=":
            return amount_value >= threshold_value
        if operator == "<":
            return amount_value < threshold_value
        if operator == "<=":
            return amount_value <= threshold_value
        return amount_value > threshold_value
    except (TypeError, ValueError):
        return False


def serialize_transaction(transaction: TransactionMaster) -> dict[str, Any]:
    return {
        "transaction_id": transaction.transaction_id,
        "transaction_date": transaction.transaction_date.isoformat(),
        "vendor_id": transaction.vendor_id,
        "amount": float(transaction.amount),
        "currency": transaction.currency,
        "transaction_type": transaction.transaction_type,
        "risk_score": float(transaction.risk_score),
        "status": transaction.status,
    }

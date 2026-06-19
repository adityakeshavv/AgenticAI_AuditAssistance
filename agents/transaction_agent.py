import sys
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.transaction_service import execute_transaction_query


class TransactionAgent:
    """First real audit agent: routes transaction questions to SQLAlchemy queries."""

    def run(
        self,
        query: str,
        *,
        routing_info: dict[str, Any] | None = None,
        db: Session | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> dict[str, Any]:
        if db is not None:
            result = execute_transaction_query(db, query, page=page, page_size=page_size)
        else:
            try:
                with SessionLocal() as session:
                    result = execute_transaction_query(session, query, page=page, page_size=page_size)
            except SQLAlchemyError as exc:
                return {
                    "success": False,
                    "selected_agent": "transaction_agent",
                    "user_query": query,
                    "error": "Database query failed. Check AUDIT_DATABASE_URL and PostgreSQL connectivity.",
                    "details": str(exc),
                }

        selected_agent = (routing_info or {}).get("agent", "transaction_agent")
        result["selected_agent"] = selected_agent
        if routing_info and routing_info.get("reason"):
            result["router_reason"] = routing_info["reason"]
        if routing_info and routing_info.get("confidence") is not None:
            result["router_confidence"] = routing_info["confidence"]
        return result


def _format_terminal_response(response: dict[str, Any]) -> str:
    lines = [
        "TRANSACTION AGENT RESPONSE",
        f"success: {response.get('success')}",
        f"reason: {response.get('reason')}",
        f"message: {response.get('message')}",
        f"outcome: {response.get('outcome')}",
        f"selected_agent: {response.get('selected_agent')}",
        f"user_query: {response.get('user_query')}",
        f"intent: {response.get('intent')}",
        f"generated_sql: {response.get('generated_sql')}",
        f"result_count: {response.get('result_count')}",
        f"page: {response.get('page')}",
        f"page_size: {response.get('page_size')}",
        "",
        "validation:",
        json.dumps(response.get("validation"), indent=2, default=str),
        "",
        "trace:",
        json.dumps(response.get("trace"), indent=2, default=str),
        "",
        "results:",
        json.dumps(response.get("results"), indent=2, default=str),
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    user_query = input("Enter transaction query: ")
    response = TransactionAgent().run(user_query)
    print(_format_terminal_response(response))

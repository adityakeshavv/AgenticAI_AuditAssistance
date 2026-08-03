import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.control_testing_service import ControlTestingService


class ControlTestingAgent:
    """Audit agent wrapper for internal control testing."""

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
            result = self._run_with_db(db, query, page=page, page_size=page_size)
        else:
            try:
                with SessionLocal() as session:
                    result = self._run_with_db(session, query, page=page, page_size=page_size)
            except SQLAlchemyError as exc:
                return {
                    "success": False,
                    "selected_agent": "control_testing_agent",
                    "user_query": query,
                    "error": "Database query failed. Check AUDIT_DATABASE_URL and PostgreSQL connectivity.",
                    "details": str(exc),
                }

        result["selected_agent"] = (routing_info or {}).get("agent", "control_testing_agent")
        if routing_info and routing_info.get("reason"):
            result["router_reason"] = routing_info["reason"]
        if routing_info and routing_info.get("confidence") is not None:
            result["router_confidence"] = routing_info["confidence"]
        return result

    def _run_with_db(self, db: Session, query: str, *, page: int, page_size: int) -> dict[str, Any]:
        return ControlTestingService(db).run(query=query, page=page, page_size=page_size)


def _format_terminal_response(response: dict[str, Any]) -> str:
    lines = [
        "CONTROL TESTING AGENT RESPONSE",
        f"success: {response.get('success')}",
        f"reason: {response.get('reason')}",
        f"message: {response.get('message')}",
        f"selected_agent: {response.get('selected_agent')}",
        f"user_query: {response.get('user_query')}",
        f"risk_rating: {response.get('risk_rating')}",
        f"risk_score: {response.get('risk_score')}",
        f"final_response: {response.get('final_response')}",
        "",
        "control_tests:",
        json.dumps(response.get("control_tests"), indent=2, default=str),
        "",
        "traceability:",
        json.dumps(response.get("traceability"), indent=2, default=str),
        "",
        "finding:",
        json.dumps(response.get("finding"), indent=2, default=str),
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    user_query = input("Enter control testing query: ")
    response = ControlTestingAgent().run(user_query)
    print(_format_terminal_response(response))

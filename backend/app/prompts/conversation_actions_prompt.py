from __future__ import annotations

import json
from typing import Any


def build_conversation_actions_messages(
    *,
    query: str,
    conversation_state: dict[str, Any],
    response_contract: dict[str, Any],
) -> list[dict[str, str]]:
    payload = {
        "query": query,
        "conversation_state": conversation_state,
        "response": {
            "risk_rating": response_contract.get("risk_rating"),
            "risk_score": response_contract.get("risk_score"),
            "finding": response_contract.get("finding", {}),
            "investigation_summary": response_contract.get("investigation_summary", ""),
            "investigation_metrics": response_contract.get("investigation_metrics", {}),
            "agents_used": response_contract.get("agents_used", []),
            "structured_evidence_count": len(response_contract.get("structured_evidence", [])),
            "document_evidence_count": len(response_contract.get("document_evidence", [])),
            "citation_count": len(response_contract.get("citations", [])),
            "supporting_documents_count": len(response_contract.get("supporting_documents", [])),
            "suggested_next_steps": response_contract.get("suggested_actions", []),
        },
    }

    return [
        {
            "role": "system",
            "content": (
                "You generate concise, context-aware next actions for an audit copilot.\n"
                "Use only the supplied investigation state and response data.\n"
                "Do not invent new evidence or unsupported actions.\n"
                "Return JSON only with this exact shape:\n"
                "{\n"
                '  "suggested_actions": [\n'
                "    {\n"
                '      "label": "Summarize findings",\n'
                '      "reason": "There are findings that can be condensed for the user.",\n'
                '      "query_hint": "Summarize the findings",\n'
                '      "action_type": "summary"\n'
                "    }\n"
                "  ]\n"
                "}\n"
                "Produce 3 to 5 actions. Keep them practical, audit-oriented, and tailored to the current investigation."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, indent=2, default=str),
        },
    ]

from __future__ import annotations

import json
from typing import Any


def build_source_router_messages(
    *,
    query: str,
    attached_document_ids: list[str] | None = None,
    memory_context: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    payload = {
        "query": query,
        "attached_document_ids": attached_document_ids or [],
        "memory_context": memory_context or {},
    }

    system = (
        "You route each user question to the most likely evidence source in an audit copilot.\n"
        "Do not answer the question.\n"
        "Decide whether the answer is most likely in:\n"
        "- pdf_only\n"
        "- db_only\n"
        "- both\n"
        "\n"
        "Guidance:\n"
        "- pdf_only when the user is asking about uploaded documents, contracts, policies, emails, or a specific file.\n"
        "- db_only when the user is asking about transactions, vendors, approvals, compliance tables, thresholds, or structured records.\n"
        "- both when the user is asking about a document AND wants verification from structured records, or the request clearly spans both.\n"
        "- Use attached documents and conversation memory as evidence clues.\n"
        "- Keep the output concise and grounded.\n"
        "- Return JSON only with this exact shape:\n"
        "{\n"
        '  "source_mode": "pdf_only|db_only|both|unknown",\n'
        '  "confidence": 0.0,\n'
        '  "reason": "Short explanation",\n'
        '  "candidate_sources": ["pdf", "database"],\n'
        '  "use_pdf": true,\n'
        '  "use_database": false\n'
        "}\n"
        "If the request is unclear, prefer 'both' when the query mentions documents and structured records, otherwise choose the most likely single source."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, indent=2, default=str)},
    ]

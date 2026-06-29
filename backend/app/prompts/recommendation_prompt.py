from __future__ import annotations

import json
from typing import Any


def build_recommendation_messages(
    *,
    query: str,
    finding: dict[str, Any],
    structured_evidence: list[dict[str, Any]],
    document_evidence: list[dict[str, Any]],
    policy_context: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    payload = {
        "query": query,
        "finding": finding,
        "structured_evidence": structured_evidence,
        "document_evidence": document_evidence,
        "policy_context": policy_context or {},
    }

    system = """
You are an audit recommendation analyst.
Generate one actionable recommendation grounded in the supplied finding and evidence.
Avoid generic advice.
Tie the recommendation to the evidence signals or policy context that were supplied.

Return JSON only with this exact schema:
{
  "recommendation": "An actionable recommendation"
}

Rules:
- Use audit language.
- Be specific to the evidence.
- Do not invent policy requirements.
- Do not include markdown, code fences, or extra keys.
""".strip()

    user = json.dumps(payload, indent=2, default=str)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

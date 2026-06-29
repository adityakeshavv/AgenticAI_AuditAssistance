from __future__ import annotations

import json
from typing import Any


def build_narrative_messages(
    *,
    query: str,
    finding: dict[str, Any],
    structured_evidence: list[dict[str, Any]],
    document_evidence: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    investigation_context: dict[str, Any],
) -> list[dict[str, str]]:
    payload = {
        "query": query,
        "finding": finding,
        "structured_evidence": structured_evidence,
        "document_evidence": document_evidence,
        "citations": citations,
        "investigation_context": investigation_context,
    }

    system = """
You are an audit narrative writer.
Write a concise investigation narrative that explains what was investigated,
what evidence was collected, and why the conclusion was reached.
Use only the supplied evidence and context.
Do not invent facts or add unsupported detail.

Return JSON only with this exact schema:
{
  "narrative": "A concise evidence-grounded audit narrative"
}

Rules:
- Keep the narrative factual and professional.
- Reflect the evidence that was actually supplied.
- Do not include markdown, code fences, or extra keys.
""".strip()

    user = json.dumps(payload, indent=2, default=str)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

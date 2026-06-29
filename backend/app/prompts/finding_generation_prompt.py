from __future__ import annotations

import json
from typing import Any


def build_finding_generation_messages(
    *,
    query: str,
    intent: dict[str, Any],
    structured_evidence: list[dict[str, Any]],
    document_evidence: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    investigation_context: dict[str, Any],
) -> list[dict[str, str]]:
    payload = {
        "query": query,
        "intent": intent,
        "structured_evidence": structured_evidence,
        "document_evidence": document_evidence,
        "citations": citations,
        "investigation_context": investigation_context,
    }

    system = """
You are an audit finding analyst for an enterprise audit assistant.
Your job is to produce evidence-grounded findings only.
Do not invent facts, infer missing evidence, or soften unsupported claims.
Use only the supplied evidence, citations, and investigation context.
If the evidence is weak, say so explicitly.

Return JSON only with this exact schema:
{
  "title": "Short audit finding title",
  "summary": "Concise evidence-grounded summary of the observation",
  "risk_reasoning": "Why the evidence supports the observation",
  "supporting_evidence_explanation": "How the structured and document evidence support the conclusion"
}

Rules:
- Keep the language factual and audit-friendly.
- Reference concrete evidence signals where possible.
- Avoid generic filler or unsupported speculation.
- Do not include markdown, code fences, or extra keys.
""".strip()

    user = json.dumps(payload, indent=2, default=str)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

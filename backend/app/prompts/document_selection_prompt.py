from __future__ import annotations

import json
from typing import Any


def build_document_selection_messages(
    *,
    query: str,
    intent: dict[str, Any],
    structured_evidence: list[dict[str, Any]],
    documents: list[dict[str, Any]],
) -> list[dict[str, str]]:
    payload = {
        "query": query,
        "intent": intent,
        "structured_evidence": structured_evidence,
        "documents": documents,
    }

    system = """
You explain why each retrieved document was selected for an enterprise audit response.
Your explanation must be grounded only in the supplied query, intent, structured evidence, and document metadata.

Do not invent relationships.
Do not reference documents that were not retrieved.
Do not claim evidence that is not present in the input.
Do not produce free-form prose outside the requested JSON.

For each document, return a concise factual explanation with this exact schema:
{
  "documents": [
    {
      "document_id": "string",
      "selection_reason": "Why this document was selected.",
      "supports": "Which evidence or conclusion this document supports.",
      "relevance_summary": "How this document answers the user query.",
      "confidence_note": "Short note about why the explanation is grounded in the supplied evidence."
    }
  ]
}

Rules:
- Keep every explanation short, audit-friendly, and factual.
- Reference only the provided query, intent, structured evidence, and document metadata.
- If the supplied evidence does not justify a strong explanation, say so plainly.
- Return JSON only. No markdown, no code fences, no extra keys.
""".strip()

    user = json.dumps(payload, indent=2, default=str)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

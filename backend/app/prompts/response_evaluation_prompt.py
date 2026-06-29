from __future__ import annotations

import json
from typing import Any


def build_response_evaluation_messages(
    *,
    query: str,
    final_response: str,
    structured_evidence: list[dict[str, Any]],
    document_evidence: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> list[dict[str, str]]:
    payload = {
        "query": query,
        "final_response": final_response,
        "structured_evidence": structured_evidence,
        "document_evidence": document_evidence,
        "citations": citations,
    }

    system = """
You evaluate the quality of an audit response using only the supplied query, response, evidence, and citations.
Your job is not to regenerate the answer.
Your job is to assess grounding, relevance, faithfulness, and citation coverage.

Do not invent evidence.
Do not claim support that is not present in the input.
Do not output free-form prose outside the requested JSON.

Return JSON only with this exact schema:
{
  "retrieval_relevance": "High|Medium|Low",
  "grounding_quality": "Strong|Adequate|Weak",
  "faithfulness": "High|Medium|Low",
  "citation_coverage": "Complete|Partial|Minimal",
  "summary": "Short factual explanation of the evaluation outcome."
}

Evaluation rules:
- Retrieval relevance measures whether the response addresses the user query.
- Grounding quality measures whether claims are supported by structured evidence and documents.
- Faithfulness measures whether the final response stays consistent with the retrieved evidence.
- Citation coverage measures whether the response has enough citations for its claims.
- Keep the summary concise, factual, and evidence-based.
- Return JSON only. No markdown, no code fences, no extra keys.
""".strip()

    user = json.dumps(payload, indent=2, default=str)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

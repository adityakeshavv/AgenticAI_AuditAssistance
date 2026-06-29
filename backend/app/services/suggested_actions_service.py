"""
SuggestedActionsService
=======================
Generates context-aware next-step suggestions after every assistant turn.
LLM-driven when an API key is available; deterministic fallback otherwise.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_DETERMINISTIC_ACTIONS: list[dict[str, str]] = [
    {"id": "summarize_findings",     "label": "Summarise Findings",          "description": "Get a concise summary of all findings so far."},
    {"id": "show_citations",         "label": "Show Citations",               "description": "List all supporting evidence and source documents."},
    {"id": "explain_risk",           "label": "Explain Risk Drivers",         "description": "Why was this rated as high/medium/low risk?"},
    {"id": "show_recommendations",   "label": "Show Recommendations",         "description": "What actions are recommended?"},
    {"id": "investigate_vendor",     "label": "Investigate Linked Vendor",    "description": "Run a full vendor investigation for the linked vendor."},
    {"id": "compare_vendors",        "label": "Compare Vendors",              "description": "Compare risk profiles across vendors."},
    {"id": "show_flagged",           "label": "Show Flagged Transactions",    "description": "List all flagged transactions from the investigation."},
    {"id": "explain_evidence",       "label": "Explain the Evidence",         "description": "Walk through each piece of supporting evidence."},
    {"id": "generate_audit_report",  "label": "Generate Audit Report",        "description": "Produce a structured audit report for this investigation."},
    {"id": "open_document",          "label": "Open Supporting Document",     "description": "View the top supporting document in detail."},
    {"id": "ask_followup",           "label": "Ask a Follow-up Question",     "description": "Continue investigating with a new question."},
]


class SuggestedActionsService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def suggest(
        self,
        *,
        query: str,
        response_contract: dict[str, Any],
        memory_context: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        if self.settings.openai_api_key:
            try:
                return self._llm_suggest(query=query, response_contract=response_contract, memory_context=memory_context or {})
            except Exception as exc:
                logger.warning("LLM suggested actions failed, using deterministic: %s", exc)
        return self._deterministic_suggest(response_contract)

    # ── LLM path ────────────────────────────────────────────────────────────

    def _llm_suggest(
        self,
        *,
        query: str,
        response_contract: dict[str, Any],
        memory_context: dict[str, Any],
    ) -> list[dict[str, str]]:
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)

        inv = memory_context.get("active_investigation", {})
        risk = response_contract.get("risk_rating", "LOW")
        key_findings = response_contract.get("key_findings", [])[:3]
        entity_type = response_contract.get("entity_type") or inv.get("entity_type") or "unknown"
        has_docs = bool(response_contract.get("document_evidence"))
        has_vendors = bool(response_contract.get("vendor_summary"))
        has_transactions = bool(response_contract.get("structured_evidence"))

        system = (
            "You are an audit copilot. Given the current audit context, suggest "
            "3-5 context-aware next actions the auditor should take.\n"
            "Each action must be specific to the current investigation, not generic.\n"
            "Return JSON only — an array:\n"
            '[{"id": "snake_case_id", "label": "Short Action Label", "description": "One sentence"}]\n'
            "No markdown, no extra keys, no prose."
        )

        ctx_text = (
            f"Query: {query}\n"
            f"Entity type: {entity_type}\n"
            f"Risk rating: {risk}\n"
            f"Key findings: {'; '.join(key_findings) or 'None'}\n"
            f"Has supporting documents: {has_docs}\n"
            f"Has vendor data: {has_vendors}\n"
            f"Has transaction data: {has_transactions}\n"
            f"Turn count: {memory_context.get('turn_count', 1)}\n"
            f"Investigation topics: {inv.get('topics', [])}"
        )

        resp = client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0.3,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": ctx_text}],
        )
        content = (resp.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        actions = json.loads(content)
        if not isinstance(actions, list):
            raise ValueError("LLM returned non-list actions")
        return [
            {
                "id": str(a.get("id", f"action_{i}")),
                "label": str(a.get("label", "Next Step")),
                "description": str(a.get("description", "")),
            }
            for i, a in enumerate(actions[:6])
            if isinstance(a, dict)
        ]

    # ── Deterministic path ───────────────────────────────────────────────────

    @staticmethod
    def _deterministic_suggest(r: dict[str, Any]) -> list[dict[str, str]]:
        actions: list[dict[str, str]] = []

        has_docs    = bool(r.get("document_evidence") or r.get("supporting_documents"))
        has_vendor  = bool(r.get("vendor_summary") or r.get("entity_type") == "vendor")
        has_tx      = bool(r.get("structured_evidence"))
        has_find    = bool(r.get("key_findings"))
        risk        = (r.get("risk_rating") or "LOW").upper()

        if has_find:
            actions.append(_DETERMINISTIC_ACTIONS[0])   # summarise findings
        if has_docs:
            actions.append(_DETERMINISTIC_ACTIONS[1])   # show citations
        if risk in ("HIGH", "CRITICAL", "MEDIUM"):
            actions.append(_DETERMINISTIC_ACTIONS[2])   # explain risk
        if has_vendor:
            actions.append(_DETERMINISTIC_ACTIONS[4])   # investigate vendor
        if has_tx:
            actions.append(_DETERMINISTIC_ACTIONS[6])   # show flagged
        if has_docs:
            actions.append(_DETERMINISTIC_ACTIONS[9])   # open document
        if has_find:
            actions.append(_DETERMINISTIC_ACTIONS[7])   # generate audit report

        if not actions:
            actions = _DETERMINISTIC_ACTIONS[:4]

        return actions[:5]

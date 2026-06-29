from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import get_settings
from app.prompts.investigation_planner_prompt import build_investigation_planner_messages


logger = logging.getLogger(__name__)


DEFAULT_AVAILABLE_AGENTS = [
    {
        "name": "transaction_agent",
        "description": "Retrieve transaction evidence and transaction-level filters.",
    },
    {
        "name": "vendor_investigation_agent",
        "description": "Investigate vendor risk, vendor profile, and vendor-related relationships.",
    },
    {
        "name": "compliance_agent",
        "description": "Review policies, compliance status, certifications, and regulatory concerns.",
    },
    {
        "name": "approval_agent",
        "description": "Analyze approval workflows, approvers, and authority limits.",
    },
    {
        "name": "document_retrieval_agent",
        "description": "Retrieve supporting document metadata and evidence snippets.",
    },
    {
        "name": "investigation_agent",
        "description": "Support cross-entity investigations and evidence synthesis.",
    },
]


class InvestigationPlannerService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def plan(
        self,
        query: str,
        *,
        intent: dict[str, Any] | None = None,
        available_agents: list[dict[str, str]] | None = None,
        investigation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = query.lower().strip()
        available_agents = available_agents or DEFAULT_AVAILABLE_AGENTS
        investigation_context = investigation_context or {}

        if not normalized:
            return self._unsupported()

        if not self.settings.openai_api_key:
            logger.warning("OPENAI_API_KEY is not configured. Falling back to heuristic investigation planning.")
            return self._heuristic_plan(normalized)

        try:
            response_text = self._call_llm(
                query,
                intent=intent or {},
                available_agents=available_agents,
                investigation_context=investigation_context,
            )
            parsed = self._parse_response(response_text, available_agents=available_agents)
            logger.info(
                "Investigation planner selected %s with %d step(s)",
                parsed.get("investigation_type"),
                len(parsed.get("plan", [])),
            )
            return parsed
        except Exception as exc:
            logger.warning("LLM investigation planning failed. Falling back to heuristic planning: %s", exc)
            return self._heuristic_plan(normalized)

    def build_execution_query(self, query: str) -> str | None:
        normalized = query.lower().strip()
        if self._looks_like_vendor_activity(normalized) or self._looks_like_vendor_risk(normalized):
            return "show suspicious transactions"
        if self._looks_like_approval_exception(normalized):
            return "show flagged transactions"
        if self._looks_like_payment_anomaly(normalized):
            return "show high-risk transactions"
        return None

    def _call_llm(
        self,
        query: str,
        *,
        intent: dict[str, Any],
        available_agents: list[dict[str, str]],
        investigation_context: dict[str, Any],
    ) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed. Run pip install -r backend/requirements.txt.") from exc

        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            messages=build_investigation_planner_messages(
                query=query,
                intent=intent,
                available_agents=available_agents,
                investigation_context=investigation_context,
            ),
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty investigation planning response.")
        return content

    def _parse_response(self, response_text: str, *, available_agents: list[dict[str, str]]) -> dict[str, Any]:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ValueError("LLM investigation planning response must be a JSON object.")

        investigation_type = str(payload.get("investigation_type") or "unsupported").strip()
        entities_required = payload.get("entities_required")
        agents_required = payload.get("agents_required")
        reasoning = payload.get("reasoning")
        plan = payload.get("plan")

        if not isinstance(entities_required, list):
            entities_required = []
        if not isinstance(agents_required, list):
            agents_required = []
        if not isinstance(reasoning, list):
            reasoning = []
        if not isinstance(plan, list):
            plan = []

        allowed_agent_names = {agent.get("name") for agent in available_agents if agent.get("name")}
        normalized_plan: list[dict[str, Any]] = []
        for step in plan:
            if not isinstance(step, dict):
                continue
            agent_name = str(step.get("agent") or "").strip()
            if agent_name not in allowed_agent_names:
                continue
            normalized_plan.append(
                {
                    "agent": agent_name,
                    "reason": str(step.get("reason") or "").strip(),
                    "expected_output": str(step.get("expected_output") or "").strip(),
                    "query_hint": str(step.get("query_hint") or "").strip(),
                }
            )

        if investigation_type == "unsupported" or not normalized_plan:
            return self._unsupported()

        return {
            "investigation_type": investigation_type,
            "entities_required": entities_required,
            "agents_required": agents_required or [step["agent"] for step in normalized_plan],
            "reasoning": [str(item).strip() for item in reasoning if str(item).strip()],
            "plan": normalized_plan,
        }

    def _heuristic_plan(self, normalized: str) -> dict[str, Any]:
        if self._looks_like_vendor_activity(normalized):
            return {
                "investigation_type": "vendor_activity_investigation",
                "entities_required": ["vendor", "transaction", "document"],
                "agents_required": ["transaction_agent", "vendor_investigation_agent", "document_retrieval_agent"],
                "reasoning": [
                    "Vendor activity review requires transaction analysis.",
                    "Transaction review requires document evidence.",
                    "Supporting evidence is required to justify the investigation findings.",
                ],
                "plan": [
                    {
                        "agent": "transaction_agent",
                        "reason": "Retrieve suspicious transaction evidence.",
                        "expected_output": "Structured transaction evidence",
                        "query_hint": "show suspicious transactions",
                    },
                    {
                        "agent": "vendor_investigation_agent",
                        "reason": "Review vendors linked to the suspicious transactions.",
                        "expected_output": "Vendor investigation evidence",
                        "query_hint": "review vendor risk",
                    },
                    {
                        "agent": "document_retrieval_agent",
                        "reason": "Retrieve supporting document evidence for the transaction and vendor trail.",
                        "expected_output": "Document citations",
                        "query_hint": "find supporting documents",
                    },
                ],
            }

        if self._looks_like_approval_exception(normalized):
            return {
                "investigation_type": "approval_exception_investigation",
                "entities_required": ["transaction", "document"],
                "agents_required": ["transaction_agent", "document_retrieval_agent"],
                "reasoning": [
                    "Approval exceptions are transaction-driven.",
                    "Supporting documents are required to validate the exception.",
                ],
                "plan": [
                    {
                        "agent": "transaction_agent",
                        "reason": "Retrieve flagged transaction evidence related to approval exceptions.",
                        "expected_output": "Structured transaction evidence",
                        "query_hint": "show flagged transactions",
                    },
                    {
                        "agent": "document_retrieval_agent",
                        "reason": "Link supporting approval documents and citations.",
                        "expected_output": "Document citations",
                        "query_hint": "find approval evidence documents",
                    },
                ],
            }

        if self._looks_like_payment_anomaly(normalized):
            return {
                "investigation_type": "payment_anomaly_investigation",
                "entities_required": ["transaction", "document"],
                "agents_required": ["transaction_agent", "document_retrieval_agent"],
                "reasoning": [
                    "Payment anomalies are best reviewed through transaction evidence.",
                    "Document evidence is required for audit support.",
                ],
                "plan": [
                    {
                        "agent": "transaction_agent",
                        "reason": "Retrieve high-risk payment evidence.",
                        "expected_output": "Structured transaction evidence",
                        "query_hint": "show high-risk transactions",
                    },
                    {
                        "agent": "document_retrieval_agent",
                        "reason": "Gather supporting payment and policy documents.",
                        "expected_output": "Document citations",
                        "query_hint": "find related policy and email evidence",
                    },
                ],
            }

        if self._looks_like_vendor_risk(normalized):
            return {
                "investigation_type": "vendor_risk_investigation",
                "entities_required": ["vendor", "transaction", "document"],
                "agents_required": ["transaction_agent", "vendor_investigation_agent", "document_retrieval_agent"],
                "reasoning": [
                    "Vendor risk review requires transaction activity analysis.",
                    "Supporting documents are needed to explain the risk drivers.",
                ],
                "plan": [
                    {
                        "agent": "transaction_agent",
                        "reason": "Retrieve the transaction trail tied to vendor risk.",
                        "expected_output": "Structured transaction evidence",
                        "query_hint": "show suspicious transactions",
                    },
                    {
                        "agent": "vendor_investigation_agent",
                        "reason": "Review vendor-level evidence derived from the transaction set.",
                        "expected_output": "Vendor investigation evidence",
                        "query_hint": "review vendor risk",
                    },
                    {
                        "agent": "document_retrieval_agent",
                        "reason": "Link documents that support the vendor risk conclusion.",
                        "expected_output": "Document citations",
                        "query_hint": "find supporting documents",
                    },
                ],
            }

        return self._unsupported()

    def _looks_like_vendor_activity(self, normalized: str) -> bool:
        return bool(
            re.search(r"\binvestigate\b.*\bsuspicious\b.*\bvendor\b", normalized)
            or re.search(r"\bvendor\b.*\bsuspicious\b.*\bactivity\b", normalized)
            or re.search(r"\breview\b.*\bvendor\b.*\brisk\b", normalized)
            or re.search(r"\banalyze\b.*\bvendor\b.*\bactivity\b", normalized)
            or re.search(r"\binvestigate\b.*\bvendor\b.*\bactivity\b", normalized)
        )

    def _looks_like_approval_exception(self, normalized: str) -> bool:
        return bool(re.search(r"\bapproval\b.*\bexception\b|\bexceptions\b.*\bapproval\b", normalized))

    def _looks_like_payment_anomaly(self, normalized: str) -> bool:
        return bool(
            re.search(r"\bpayment\b.*\banomal", normalized)
            or re.search(r"\banomal", normalized)
            or re.search(r"\bpayment\b.*\bsuspicious\b", normalized)
        )

    def _looks_like_vendor_risk(self, normalized: str) -> bool:
        return bool(
            re.search(r"\bvendor\b.*\brisk\b", normalized)
            or re.search(r"\brisk\b.*\bvendor\b", normalized)
            or re.search(r"\binvestigate\b.*\bvendor\b", normalized)
        )

    def _unsupported(self) -> dict[str, Any]:
        return {
            "investigation_type": "unsupported",
            "entities_required": [],
            "agents_required": [],
            "reasoning": [
                "The query could not be mapped to a supported investigation scenario.",
            ],
            "plan": [],
        }

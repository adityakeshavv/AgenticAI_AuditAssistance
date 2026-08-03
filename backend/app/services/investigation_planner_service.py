from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import get_settings
from app.services.gemini_client_service import GeminiClientService
from app.prompts.investigation_planner_prompt import build_investigation_planner_messages


logger = logging.getLogger(__name__)


DEFAULT_AVAILABLE_AGENTS = [
    {
        "name": "transaction_agent",
        "description": "Retrieve transaction evidence and transaction-level filters.",
    },
    {
        "name": "control_testing_agent",
        "description": "Run internal control tests for approvals, segregation of duties proxies, policy exceptions, duplicate payments, and failed controls.",
    },
    {
        "name": "vendor_investigation_agent",
        "description": "Investigate vendor risk, vendor profile, and vendor-related relationships.",
    },
    {
        "name": "compliance_agent",
        "description": "Review vendor compliance records, certifications, expired assessments, and regulatory framework status (SOX, GDPR, ISO 27001, etc).",
    },
    {
        "name": "approval_agent",
        "description": "Analyze approval workflows, approvers, authority limits, escalations, and rejected approvals. Use when the query concerns who approved something, approval exceptions, or authority limits.",
    },
    {
        "name": "expense_agent",
        "description": "Review employee expense claims, flagged claims, missing receipts, and travel/expense policy violations.",
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
        self.gemini_client = GeminiClientService()

    def plan(
        self,
        query: str,
        *,
        intent: dict[str, Any] | None = None,
        available_agents: list[dict[str, str]] | None = None,
        investigation_context: dict[str, Any] | None = None,
        trace_context: Any | None = None,
    ) -> dict[str, Any]:
        normalized = query.lower().strip()
        available_agents = available_agents or DEFAULT_AVAILABLE_AGENTS
        investigation_context = investigation_context or {}
        plan_span = trace_context.begin_span(
            "investigation_planner",
            input_payload={
                "query": query,
                "intent": intent or {},
                "available_agents": available_agents,
                "investigation_context": investigation_context,
            },
            metadata={"service": "InvestigationPlannerService"},
        ) if trace_context else None

        if not normalized:
            unsupported = self._unsupported()
            if plan_span:
                plan_span.finish(output=unsupported, metadata={"investigation_type": unsupported.get("investigation_type")})
            return unsupported

        if self.settings.agent_runtime == "gemini_adk" and self.gemini_client.is_configured():
            try:
                llm_span = trace_context.begin_span(
                    "investigation_planner_llm",
                    input_payload={
                        "query": query,
                        "intent": intent or {},
                        "available_agents": available_agents,
                        "investigation_context": investigation_context,
                    },
                    metadata={"service": "InvestigationPlannerService", "model": self.settings.gemini_model},
                ) if trace_context else None
                response_text = self.gemini_client.generate_json(
                    system_prompt=self._gemini_system_prompt(
                        intent=intent or {},
                        available_agents=available_agents,
                        investigation_context=investigation_context,
                    ),
                    user_prompt=query,
                    model=self.settings.gemini_model,
                )
                parsed = self._parse_response(response_text, available_agents=available_agents)
                if llm_span:
                    llm_span.finish(
                        output=response_text,
                        metadata={"service": "InvestigationPlannerService", "runtime": "gemini", "model": self.settings.gemini_model},
                    )
                logger.info(
                    "Gemini investigation planner selected %s with %d step(s)",
                    parsed.get("investigation_type"),
                    len(parsed.get("plan", [])),
                )
                if plan_span:
                    plan_span.finish(output=parsed, metadata={"investigation_type": parsed.get("investigation_type"), "step_count": len(parsed.get("plan", []))})
                return parsed
            except Exception as exc:
                logger.warning("Gemini investigation planning failed. Falling back to heuristic planning: %s", exc)

        if not self.settings.openai_api_key:
            logger.warning("OPENAI_API_KEY is not configured. Falling back to heuristic investigation planning.")
            fallback = self._heuristic_plan(normalized)
            if plan_span:
                plan_span.finish(output=fallback, metadata={"investigation_type": fallback.get("investigation_type"), "runtime": "heuristic"})
            return fallback

        try:
            response_text = self._call_llm(
                query,
                intent=intent or {},
                available_agents=available_agents,
                investigation_context=investigation_context,
                trace_context=trace_context,
            )
            parsed = self._parse_response(response_text, available_agents=available_agents)
            logger.info(
                "Investigation planner selected %s with %d step(s)",
                parsed.get("investigation_type"),
                len(parsed.get("plan", [])),
            )
            if plan_span:
                plan_span.finish(output=parsed, metadata={"investigation_type": parsed.get("investigation_type"), "step_count": len(parsed.get("plan", []))})
            return parsed
        except Exception as exc:
            logger.warning("LLM investigation planning failed. Falling back to heuristic planning: %s", exc)
            fallback = self._heuristic_plan(normalized)
            if plan_span:
                plan_span.finish(output=fallback, metadata={"investigation_type": fallback.get("investigation_type"), "runtime": "heuristic"}, error=str(exc))
            return fallback

    def build_execution_query(self, query: str) -> str | None:
        normalized = query.lower().strip()
        if self._looks_like_control_review(normalized):
            return "show flagged transactions"
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
        trace_context: Any | None = None,
    ) -> str:
        if self.settings.agent_runtime == "gemini_adk" and self.gemini_client.is_configured():
            llm_span = trace_context.begin_span(
                "investigation_planner_llm",
                input_payload={
                    "query": query,
                    "intent": intent,
                    "available_agents": available_agents,
                    "investigation_context": investigation_context,
                },
                metadata={"service": "InvestigationPlannerService", "model": self.settings.gemini_model},
            ) if trace_context else None
            response_text = self.gemini_client.generate_json(
                system_prompt=self._gemini_system_prompt(
                    intent=intent,
                    available_agents=available_agents,
                    investigation_context=investigation_context,
                ),
                user_prompt=query,
                model=self.settings.gemini_model,
            )
            if llm_span:
                llm_span.finish(
                    output=response_text,
                    metadata={"service": "InvestigationPlannerService", "runtime": "gemini", "model": self.settings.gemini_model},
                )
            return response_text

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed. Run pip install -r backend/requirements.txt.") from exc

        client = OpenAI(api_key=self.settings.openai_api_key)
        llm_span = trace_context.begin_span(
            "investigation_planner_llm",
            input_payload=build_investigation_planner_messages(
                query=query,
                intent=intent,
                available_agents=available_agents,
                investigation_context=investigation_context,
            ),
            metadata={"service": "InvestigationPlannerService", "model": self.settings.openai_model},
        ) if trace_context else None
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
        usage = getattr(response, "usage", None)
        usage_payload = {}
        if usage is not None:
            usage_payload = {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
        if llm_span:
            llm_span.finish(
                output=content,
                metadata={"service": "InvestigationPlannerService", "usage": usage_payload, "model": self.settings.openai_model},
            )
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

    def _gemini_system_prompt(
        self,
        *,
        intent: dict[str, Any],
        available_agents: list[dict[str, str]],
        investigation_context: dict[str, Any],
    ) -> str:
        agents_text = "\n".join(
            f"- {agent.get('name')}: {agent.get('description', '')}" for agent in available_agents if agent.get("name")
        )
        intent_text = json.dumps(intent or {}, indent=2, default=str)
        context_text = json.dumps(investigation_context or {}, indent=2, default=str)
        return f"""
You are the investigation planner for an enterprise audit copilot.
Use Gemini-style reasoning to decide which agents are needed and in what order.
Plan evidence-first workflows. Do not force every query into the same path.
Return JSON only.

Available agents:
{agents_text}

Current intent:
{intent_text}

Investigation context:
{context_text}

Return exactly this shape:
{{
  "investigation_type": "short_name",
  "entities_required": ["transaction", "vendor"],
  "agents_required": ["transaction_agent", "document_retrieval_agent"],
  "reasoning": ["Why this plan is needed."],
  "plan": [
    {{
      "agent": "transaction_agent",
      "reason": "Retrieve structured transaction evidence.",
      "expected_output": "Structured transaction evidence",
      "query_hint": "optional execution query hint"
    }}
  ]
}}

If the query cannot be investigated, return:
{{
  "investigation_type": "unsupported",
  "entities_required": [],
  "agents_required": [],
  "reasoning": ["Why the request cannot be investigated."],
  "plan": []
}}
Do not include markdown or extra keys.
""".strip()

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

        if self._looks_like_control_review(normalized):
            return {
                "investigation_type": "control_testing_investigation",
                "entities_required": ["transaction", "approval_workflow", "compliance_record", "document"],
                "agents_required": ["control_testing_agent", "document_retrieval_agent"],
                "reasoning": [
                    "Control testing requires structured checks across transactions, approvals, and compliance evidence.",
                    "Document evidence is required to support control exceptions and audit conclusions.",
                ],
                "plan": [
                    {
                        "agent": "control_testing_agent",
                        "reason": "Run baseline internal control tests across the available structured audit data.",
                        "expected_output": "Structured control testing evidence",
                        "query_hint": "run control testing",
                    },
                    {
                        "agent": "document_retrieval_agent",
                        "reason": "Link supporting control evidence and citations.",
                        "expected_output": "Document citations",
                        "query_hint": "find supporting control documents",
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

        if self._looks_like_compliance_review(normalized):
            return {
                "investigation_type": "compliance_review_investigation",
                "entities_required": ["vendor", "compliance_record", "document"],
                "agents_required": ["compliance_agent", "document_retrieval_agent"],
                "reasoning": [
                    "Compliance review requires checking vendor certification and framework status.",
                    "Supporting documents are required to validate compliance findings.",
                ],
                "plan": [
                    {
                        "agent": "compliance_agent",
                        "reason": "Retrieve compliance records matching the query (expired, non-compliant, or framework-specific).",
                        "expected_output": "Structured compliance evidence",
                        "query_hint": "show expired compliance records",
                    },
                    {
                        "agent": "document_retrieval_agent",
                        "reason": "Link supporting compliance documentation and citations.",
                        "expected_output": "Document citations",
                        "query_hint": "find compliance evidence documents",
                    },
                ],
            }

        if self._looks_like_approval_review(normalized):
            return {
                "investigation_type": "approval_review_investigation",
                "entities_required": ["transaction", "approval_workflow", "document"],
                "agents_required": ["approval_agent", "document_retrieval_agent"],
                "reasoning": [
                    "Approval review requires checking authority limits and approval status.",
                    "Supporting documents are required to validate the approval trail.",
                ],
                "plan": [
                    {
                        "agent": "approval_agent",
                        "reason": "Retrieve approval workflow evidence matching the query.",
                        "expected_output": "Structured approval evidence",
                        "query_hint": "show approvals that exceeded authority",
                    },
                    {
                        "agent": "document_retrieval_agent",
                        "reason": "Link supporting approval evidence and citations.",
                        "expected_output": "Document citations",
                        "query_hint": "find approval evidence documents",
                    },
                ],
            }

        if self._looks_like_expense_review(normalized):
            return {
                "investigation_type": "expense_review_investigation",
                "entities_required": ["employee", "expense_claim", "document"],
                "agents_required": ["expense_agent", "document_retrieval_agent"],
                "reasoning": [
                    "Expense review requires checking flagged claims, missing receipts, or policy violations.",
                    "Supporting documents are required to validate expense findings.",
                ],
                "plan": [
                    {
                        "agent": "expense_agent",
                        "reason": "Retrieve expense claim evidence matching the query.",
                        "expected_output": "Structured expense evidence",
                        "query_hint": "show flagged expense claims",
                    },
                    {
                        "agent": "document_retrieval_agent",
                        "reason": "Link supporting receipts and policy documents.",
                        "expected_output": "Document citations",
                        "query_hint": "find expense policy evidence documents",
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

    def _looks_like_control_review(self, normalized: str) -> bool:
        return bool(
            re.search(r"\bcontrol\b", normalized)
            or re.search(r"\bcontrols\b", normalized)
            or re.search(r"\bcontrol testing\b", normalized)
            or re.search(r"\btest controls\b", normalized)
            or re.search(r"\binternal control\b", normalized)
            or re.search(r"\bsegregation of duties\b", normalized)
            or re.search(r"\bpolicy exception\b", normalized)
            or re.search(r"\bduplicate payment\b", normalized)
        )

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

    def _looks_like_compliance_review(self, normalized: str) -> bool:
        return bool(
            re.search(r"\bcompliance\b", normalized)
            or re.search(r"\bcertification\b", normalized)
            or re.search(r"\bexpired\b.*\b(?:compliance|certification|documentation)\b", normalized)
            or re.search(r"\b(?:sox|gdpr|hipaa|iso\s*27001|iso\s*9001|pci[- ]dss|soc\s*2|cmmc|nist)\b", normalized)
            or re.search(r"\bregulatory\b", normalized)
        )

    def _looks_like_approval_review(self, normalized: str) -> bool:
        return bool(
            re.search(r"\bapprov(?:al|er|ed)\b", normalized)
            or re.search(r"\bauthority\s+limit\b", normalized)
            or re.search(r"\bescalat(?:ed|ion)\b", normalized)
            or re.search(r"\bexceeded\b.*\b(?:limit|authority)\b", normalized)
        )

    def _looks_like_expense_review(self, normalized: str) -> bool:
        return bool(
            re.search(r"\bexpense\b", normalized)
            or re.search(r"\btravel\s+(?:claim|policy|expense)\b", normalized)
            or re.search(r"\breceipt\b", normalized)
            or re.search(r"\bclaim\b.*\bviolat", normalized)
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

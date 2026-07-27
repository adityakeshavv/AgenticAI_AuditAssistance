import json
import logging
from typing import Any, Protocol

from app.core.config import get_settings
from app.services.gemini_client_service import GeminiClientService


logger = logging.getLogger(__name__)


VALID_AGENTS = {
    "transaction_agent",
    "vendor_agent",
    "compliance_agent",
    "approval_agent",
    "expense_agent",
    "investigation_agent",
    "general_agent",
}


class FallbackRouter(Protocol):
    def route(self, query: str) -> dict[str, Any]:
        ...


class LLMRouterService:
    """OpenAI-compatible semantic router with keyword fallback."""

    def __init__(self, fallback_router: FallbackRouter | None = None) -> None:
        self.settings = get_settings()
        self.fallback_router = fallback_router
        self.gemini_client = GeminiClientService()

    def route(self, query: str, trace_context: Any | None = None) -> dict[str, Any]:
        if self.settings.agent_runtime == "gemini_adk" and self.gemini_client.is_configured():
            llm_span = None
            try:
                llm_span = trace_context.begin_span(
                    "query_router_llm",
                    input_payload={"system_prompt": self._system_prompt(), "user_prompt": query},
                    metadata={"service": "LLMRouterService", "model": self.settings.gemini_model},
                ) if trace_context else None
                response_text = self.gemini_client.generate_json(
                    system_prompt=self._system_prompt(),
                    user_prompt=query,
                    model=self.settings.gemini_model,
                )
                parsed = self._parse_response(response_text)
                parsed.setdefault("decision_source", "llm")
                parsed.setdefault("candidate_agents", [parsed["agent"]])
                parsed.setdefault("escalate_to_planner", parsed["agent"] == "general_agent" or parsed["confidence"] < 0.75)
                if llm_span:
                    llm_span.finish(output=response_text, metadata={"service": "LLMRouterService", "model": self.settings.gemini_model})
                logger.info("Gemini router selected %s with confidence %.2f", parsed["agent"], parsed["confidence"])
                return parsed
            except Exception as exc:
                if llm_span:
                    llm_span.finish(output={"error": str(exc)}, metadata={"service": "LLMRouterService", "model": self.settings.gemini_model}, error=str(exc))
                logger.warning("Gemini router failed. Falling back to OpenAI/keyword router: %s", exc)

        if not self.settings.openai_api_key:
            logger.warning("OPENAI_API_KEY is not configured. Falling back to keyword router.")
            return self._fallback(query, "OPENAI_API_KEY is not configured.")

        try:
            response_text = self._call_llm(query, trace_context=trace_context)
            parsed = self._parse_response(response_text)
            parsed.setdefault("decision_source", "llm")
            parsed.setdefault("candidate_agents", [parsed["agent"]])
            parsed.setdefault("escalate_to_planner", parsed["agent"] == "general_agent" or parsed["confidence"] < 0.75)
            logger.info("LLM router selected %s with confidence %.2f", parsed["agent"], parsed["confidence"])
            return parsed
        except Exception as exc:
            logger.warning("LLM router failed. Falling back to keyword router: %s", exc)
            return self._fallback(query, f"LLM router failed: {exc}")

    def _call_llm(self, query: str, trace_context: Any | None = None) -> str:
        if self.settings.agent_runtime == "gemini_adk" and self.gemini_client.is_configured():
            llm_span = trace_context.begin_span(
                "query_router_llm",
                input_payload={"system_prompt": self._system_prompt(), "user_prompt": query},
                metadata={"service": "StructuredIntentService", "model": self.settings.gemini_model},
            ) if trace_context else None
            response_text = self.gemini_client.generate_json(
                system_prompt=self._system_prompt(),
                user_prompt=query,
                model=self.settings.gemini_model,
            )
            if llm_span:
                llm_span.finish(output=response_text, metadata={"service": "StructuredIntentService", "model": self.settings.gemini_model})
            return response_text

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed. Run pip install -r backend/requirements.txt.") from exc

        client = OpenAI(api_key=self.settings.openai_api_key)
        llm_span = trace_context.begin_span(
            "query_router_llm",
            input_payload={"system_prompt": self._system_prompt(), "user_prompt": query},
            metadata={"service": "LLMRouterService", "model": self.settings.openai_model},
        ) if trace_context else None
        try:
            response = client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": self._system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": query,
                    },
                ],
            )
        except Exception as exc:
            if llm_span:
                llm_span.finish(output={"error": str(exc)}, metadata={"service": "LLMRouterService", "model": self.settings.openai_model}, error=str(exc))
            raise

        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty routing response.")
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
                metadata={"service": "LLMRouterService", "usage": usage_payload, "model": self.settings.openai_model},
            )
        return content

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        payload = json.loads(cleaned)

        agent = payload.get("agent")
        confidence = float(payload.get("confidence", 0))
        reason = payload.get("reason")
        candidate_agents = payload.get("candidate_agents")
        escalate_to_planner = bool(payload.get("escalate_to_planner", False))

        if agent not in VALID_AGENTS:
            raise ValueError(f"Invalid agent returned by LLM: {agent}")
        if confidence < 0 or confidence > 1:
            raise ValueError(f"Invalid confidence returned by LLM: {confidence}")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("LLM response must include a non-empty reason.")
        if candidate_agents is None:
            candidate_agents = [agent]
        if not isinstance(candidate_agents, list) or not all(isinstance(item, str) and item in VALID_AGENTS for item in candidate_agents):
            raise ValueError("LLM response candidate_agents must be a list of valid agent names.")

        return {
            "agent": agent,
            "confidence": confidence,
            "reason": reason.strip(),
            "candidate_agents": list(dict.fromkeys(candidate_agents)),
            "escalate_to_planner": escalate_to_planner or confidence < 0.75 or agent == "general_agent",
            "decision_source": "llm",
        }

    def _fallback(self, query: str, reason: str) -> dict[str, Any]:
        if self.fallback_router is None:
            return {
                "agent": "general_agent",
                "confidence": 0.50,
                "reason": reason,
                "candidate_agents": ["general_agent"],
                "escalate_to_planner": True,
                "decision_source": "keyword_fallback",
            }

        result = self.fallback_router.route(query)
        return {
            "agent": result.get("agent", "general_agent"),
            "confidence": result.get("confidence", 0.50),
            "reason": f"{reason} Fallback reason: {result.get('reason', 'Keyword fallback selected route.')}",
            "candidate_agents": list(result.get("candidate_agents") or [result.get("agent", "general_agent")]),
            "escalate_to_planner": bool(result.get("escalate_to_planner", False) or result.get("agent") == "general_agent"),
            "decision_source": str(result.get("decision_source", "keyword_fallback")),
        }

    @staticmethod
    def _system_prompt() -> str:
        return """
You are an intent router for an enterprise audit assistant.
Classify the user's query into exactly one available agent.

Available agents:
- transaction_agent: payments, transactions, suspicious payments, duplicate invoices, fraud patterns, high-risk transactions, amounts, transaction status.
- vendor_agent: vendors, suppliers, vendor risk, vendor profile, vendor status, vendor contracts.
- compliance_agent: compliance status, expired certifications, certifications, policies, regulatory violations, compliance frameworks.
- approval_agent: approvals, approvers, approval workflow, authority limits, who approved a transaction.
- expense_agent: expense claims, travel policy violations, missing receipts, flagged expenses, reimbursement.
- investigation_agent: audit investigations, findings, evidence, citations, traceability, finding support.
- general_agent: use only when none of the above are appropriate.

Routing guidance:
- Prefer escalation when the query is ambiguous, multi-domain, or could reasonably require more than one agent.
- Use general_agent for unrelated, nonsensical, or out-of-domain questions.
- Do not guess when the query is merely a keyword match without audit context.
- Example ambiguous cases that should escalate: "show vendor compliance issues for flagged transactions", "review approvals and expenses", "investigate supplier risk and policy violations".
- Example unsupported cases that should escalate: "tell me a joke", "what is the capital of france", "how is the weather today", "who won the cricket match".

Return JSON only with this exact shape:
{
  "agent": "transaction_agent",
  "confidence": 0.95,
  "reason": "Short reason for the selected agent.",
  "candidate_agents": ["transaction_agent"],
  "escalate_to_planner": false
}

Do not include markdown, prose, or extra keys.
""".strip()


class StructuredIntentService:
    """Reusable semantic intent extraction for audit queries."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def extract(
        self,
        query: str,
        *,
        domain: str,
        entity: str,
        allowed_intents: list[str],
        trace_context: Any | None = None,
    ) -> dict[str, Any]:
        extraction_span = trace_context.begin_span(
            "query_router_intent",
            input_payload={"query": query, "domain": domain, "entity": entity, "allowed_intents": allowed_intents},
            metadata={"service": "StructuredIntentService"},
        ) if trace_context else None

        if not self.settings.openai_api_key:
            logger.warning("OPENAI_API_KEY is not configured. Returning unsupported structured intent.")
            unsupported = self._unsupported_intent(query, domain, entity, "OPENAI_API_KEY is not configured.")
            if extraction_span:
                extraction_span.finish(output=unsupported, metadata={"supported": False, "reason": unsupported.get("reason")})
            return unsupported

        try:
            response_text = self._call_llm(
                query,
                domain=domain,
                entity=entity,
                allowed_intents=allowed_intents,
                trace_context=trace_context,
            )
            parsed = self._parse_response(
                response_text,
                original_query=query,
                domain=domain,
                entity=entity,
                allowed_intents=allowed_intents,
            )
            logger.info("Intent extraction produced intent=%s supported=%s", parsed.get("intent"), parsed.get("supported"))
            if extraction_span:
                extraction_span.finish(output=parsed, metadata={"supported": parsed.get("supported"), "intent": parsed.get("intent")})
            return parsed
        except Exception as exc:
            logger.warning("Intent extraction failed. Returning unsupported structured intent: %s", exc)
            unsupported = self._unsupported_intent(query, domain, entity, f"Intent extraction failed: {exc}")
            if extraction_span:
                extraction_span.finish(output=unsupported, metadata={"supported": False, "reason": unsupported.get("reason")}, error=str(exc))
            return unsupported

    def _call_llm(self, query: str, *, domain: str, entity: str, allowed_intents: list[str], trace_context: Any | None = None) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed. Run pip install -r backend/requirements.txt.") from exc

        client = OpenAI(api_key=self.settings.openai_api_key)
        llm_span = trace_context.begin_span(
            "query_router_llm",
            input_payload={"system_prompt": self._system_prompt(domain=domain, entity=entity, allowed_intents=allowed_intents), "user_prompt": query},
            metadata={"service": "StructuredIntentService", "model": self.settings.openai_model},
        ) if trace_context else None
        response = client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": self._system_prompt(domain=domain, entity=entity, allowed_intents=allowed_intents),
                },
                {
                    "role": "user",
                    "content": query,
                },
            ],
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty intent extraction response.")
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
                metadata={"service": "StructuredIntentService", "usage": usage_payload, "model": self.settings.openai_model},
            )
        return content

    def _parse_response(
        self,
        response_text: str,
        *,
        original_query: str,
        domain: str,
        entity: str,
        allowed_intents: list[str],
    ) -> dict[str, Any]:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        payload = json.loads(cleaned)

        supported = bool(payload.get("supported", False))
        intent = payload.get("intent")
        normalized_query = payload.get("normalized_query") or original_query.strip().lower()
        confidence = float(payload.get("confidence", 0.0))
        reason = payload.get("reason")
        filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
        query_type = payload.get("query_type") or "list"
        extracted_domain = payload.get("domain") or domain
        extracted_entity = payload.get("entity") or entity

        if extracted_domain != domain:
            supported = False
        if extracted_entity != entity:
            supported = False
        if intent not in allowed_intents:
            supported = False
        if confidence < 0 or confidence > 1:
            raise ValueError(f"Invalid confidence returned by LLM: {confidence}")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("LLM response must include a non-empty reason.")

        if not supported:
            intent = None

        return {
            "original_query": original_query,
            "normalized_query": str(normalized_query).strip().lower(),
            "domain": extracted_domain,
            "entity": extracted_entity,
            "intent": intent,
            "query_type": query_type,
            "filters": filters,
            "supported": supported,
            "confidence": confidence,
            "reason": reason.strip(),
        }

    def _unsupported_intent(self, query: str, domain: str, entity: str, reason: str) -> dict[str, Any]:
        return {
            "original_query": query,
            "normalized_query": query.strip().lower(),
            "domain": domain,
            "entity": entity,
            "intent": None,
            "query_type": "list",
            "filters": {},
            "supported": False,
            "confidence": 0.0,
            "reason": reason,
        }

    @staticmethod
    def _system_prompt(*, domain: str, entity: str, allowed_intents: list[str]) -> str:
        allowed = "\n".join(f"- {intent}" for intent in allowed_intents)
        return f"""
You extract structured business intent for an enterprise audit assistant.
Do not generate SQL.
Return JSON only.

Domain: {domain}
Entity: {entity}

Allowed intents:
{allowed}

For comparison-based queries, use one reusable intent and express the business condition through filters.
Prefer the generic filtered intent when the query can be represented with comparison filters.
Comparison filters should use the shape:
{{
  "field_name": {{
    "operator": ">",
    "value": 1000
  }}
}}

The operator must be one of: >, >=, <, <=.
Use canonical, normalized business language in normalized_query.

Return exactly this JSON shape:
{{
  "original_query": "The user's original query.",
  "normalized_query": "A concise canonical business paraphrase.",
  "domain": "{domain}",
  "entity": "{entity}",
  "intent": "one of the allowed intents, or null if unsupported",
  "query_type": "list",
  "filters": {{
    "amount": {{
      "operator": "<",
      "value": 1000
    }}
  }},
  "supported": true,
  "confidence": 0.95,
  "reason": "Short explanation of the mapping."
}}

If the query is unsupported, ambiguous, or cannot be mapped to one of the allowed intents, set supported to false and intent to null.
Do not include markdown, prose, or extra keys.
""".strip()

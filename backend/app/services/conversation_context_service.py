from __future__ import annotations

import copy
import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.prompts.conversation_actions_prompt import build_conversation_actions_messages


logger = logging.getLogger(__name__)

_CONVERSATION_STORE: dict[str, dict[str, Any]] = {}
_STORE_LOCK = threading.Lock()

_FOLLOW_UP_PATTERNS = (
    r"\bwhy\b.*\b(these|those|they|them|it|that|this)\b",
    r"\bexplain\b",
    r"\bsummarize\b",
    r"\bshow\b.*\bcitation",
    r"\bshow\b.*\bevidence",
    r"\bopen\b.*\bdocument",
    r"\bwhat about\b",
    r"\bcompare\b.*\bthem\b",
    r"\bmore detail\b",
    r"\bwhat were\b",
    r"\bwhich ones\b",
)


class ConversationContextService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def initialize(self, conversation_id: str | None, query: str) -> dict[str, Any]:
        state = self.get_state(conversation_id)
        state.setdefault("recent_queries", [])
        state.setdefault("turn_count", 0)
        state.setdefault("current_topic", "")
        state.setdefault("status", "NEW")
        state.setdefault("active_entities", {"transactions": [], "vendors": [], "documents": [], "contracts": []})
        state.setdefault("evidence_counts", {"structured": 0, "documents": 0, "citations": 0})
        state.setdefault("finding_count", 0)
        state.setdefault("last_summary", "")
        state.setdefault("last_query", "")
        state.setdefault("last_response_snapshot", {})
        state.setdefault("last_agents", [])
        state.setdefault("updated_at", self._timestamp())
        state["turn_count"] = int(state.get("turn_count", 0)) + 1
        state["last_query"] = query
        state["recent_queries"] = (list(state.get("recent_queries", [])) + [query])[-10:]
        state["updated_at"] = self._timestamp()
        self._save_state(state)
        return state

    def get_state(self, conversation_id: str | None) -> dict[str, Any]:
        if conversation_id and conversation_id in _CONVERSATION_STORE:
            return copy.deepcopy(_CONVERSATION_STORE[conversation_id])

        conversation_id = conversation_id or self._generate_conversation_id()
        state = self._new_state(conversation_id)
        self._save_state(state)
        return copy.deepcopy(state)

    def build_investigation_context(self, *, query: str, state: dict[str, Any]) -> dict[str, Any]:
        follow_up = self.resolve_follow_up(query=query, state=state)
        return {
            "conversation_id": state.get("conversation_id"),
            "follow_up": follow_up,
            "conversation_state": self.build_workspace(state),
            "recent_queries": list(state.get("recent_queries", [])),
            "last_summary": state.get("last_summary", ""),
            "active_entities": copy.deepcopy(state.get("active_entities", {})),
            "turn_count": int(state.get("turn_count", 0)),
            "status": state.get("status", "NEW"),
        }

    def resolve_follow_up(self, *, query: str, state: dict[str, Any]) -> dict[str, Any]:
        normalized = query.strip().lower()
        is_follow_up = bool(state.get("last_response_snapshot")) and any(
            re.search(pattern, normalized) for pattern in _FOLLOW_UP_PATTERNS
        )
        if not is_follow_up:
            return {
                "is_follow_up": False,
                "should_reuse_context": False,
                "resolved_query": query,
                "reason": "No conversational follow-up reference was detected.",
            }

        topic = str(state.get("current_topic") or "the active investigation").strip()
        last_summary = str(state.get("last_summary") or "").strip()
        active_entities = self._format_active_entities(state.get("active_entities", {}))
        resolved_query = (
            f"Follow-up on {topic}: {query.strip()}. "
            f"Active entities: {active_entities}. "
            f"Previous summary: {last_summary or 'No prior summary captured.'}"
        ).strip()
        return {
            "is_follow_up": True,
            "should_reuse_context": True,
            "resolved_query": resolved_query,
            "reason": "The query references the prior investigation context and can be answered from stored evidence.",
        }

    def build_workspace(self, state: dict[str, Any]) -> dict[str, Any]:
        active_entities = state.get("active_entities", {})
        evidence_counts = state.get("evidence_counts", {})
        return {
            "conversation_id": state.get("conversation_id"),
            "current_topic": state.get("current_topic") or "General audit inquiry",
            "status": state.get("status") or "NEW",
            "turn_count": int(state.get("turn_count", 0)),
            "last_query": state.get("last_query") or "",
            "last_summary": state.get("last_summary") or "",
            "updated_at": state.get("updated_at") or self._timestamp(),
            "active_entities": copy.deepcopy(active_entities),
            "evidence_counts": {
                "structured": int(evidence_counts.get("structured", 0)),
                "documents": int(evidence_counts.get("documents", 0)),
                "citations": int(evidence_counts.get("citations", 0)),
            },
            "finding_count": int(state.get("finding_count", 0)),
        }

    def update_from_response(self, *, state: dict[str, Any], response_contract: dict[str, Any]) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["updated_at"] = self._timestamp()
        updated["last_response_snapshot"] = self._snapshot_response(response_contract)
        updated["last_query"] = response_contract.get("query") or state.get("last_query") or ""
        updated["recent_queries"] = (list(state.get("recent_queries", [])) + [updated["last_query"]])[-10:]
        updated["last_agents"] = list(response_contract.get("agents_used", []))

        topic = self._infer_topic(response_contract)
        if topic:
            updated["current_topic"] = topic

        entities = self._infer_entities(response_contract)
        if entities:
            updated["active_entities"] = entities

        structured_count = len(response_contract.get("structured_evidence", []))
        document_count = len(response_contract.get("document_evidence", []))
        citation_count = len(response_contract.get("citations", []))
        updated["evidence_counts"] = {
            "structured": structured_count,
            "documents": document_count,
            "citations": citation_count,
        }
        updated["finding_count"] = self._count_findings(response_contract)
        updated["last_summary"] = self._summarize_response(response_contract)
        updated["status"] = "IN_PROGRESS" if response_contract.get("success", True) else "REVIEW_REQUIRED"
        self._save_state(updated)
        return copy.deepcopy(updated)

    def build_follow_up_response(
        self,
        *,
        query: str,
        state: dict[str, Any],
        conversation_state: dict[str, Any],
    ) -> dict[str, Any]:
        snapshot = copy.deepcopy(state.get("last_response_snapshot") or {})
        if not snapshot:
            return {}

        snapshot["query"] = query
        snapshot["conversation_id"] = conversation_state.get("conversation_id")
        snapshot["conversation_state"] = self.build_workspace(state)
        snapshot["suggested_actions"] = []
        snapshot["message"] = None
        snapshot["traceability"] = snapshot.get("traceability", {}) or {}
        snapshot["traceability"].setdefault("reasoning_path", [])
        snapshot["traceability"]["reasoning_path"] = list(snapshot["traceability"].get("reasoning_path", [])) + [
            "The follow-up question was resolved against the active conversation memory.",
        ]
        snapshot["reasoning"] = list(snapshot.get("reasoning", [])) + [
            "The assistant reused the prior investigation context to answer the follow-up.",
        ]
        snapshot["conversation_state"]["last_query"] = query
        return snapshot

    def generate_suggested_actions(
        self,
        *,
        query: str,
        state: dict[str, Any],
        response_contract: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not query.strip():
            return []

        if self.settings.openai_api_key:
            try:
                return self._generate_actions_with_llm(query=query, state=state, response_contract=response_contract)
            except Exception as exc:
                logger.warning("LLM suggested-action generation failed. Falling back to deterministic actions: %s", exc)

        return self._fallback_actions(state=state, response_contract=response_contract)

    def _generate_actions_with_llm(
        self,
        *,
        query: str,
        state: dict[str, Any],
        response_contract: dict[str, Any],
    ) -> list[dict[str, Any]]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed. Run pip install -r backend/requirements.txt.") from exc

        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            messages=build_conversation_actions_messages(
                query=query,
                conversation_state=self.build_workspace(state),
                response_contract=response_contract,
            ),
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty suggested actions response.")

        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        payload = json.loads(cleaned)
        actions = payload.get("suggested_actions", [])
        if not isinstance(actions, list):
            raise ValueError("Suggested actions response must contain a suggested_actions list.")

        normalized: list[dict[str, Any]] = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            label = str(action.get("label") or "").strip()
            reason = str(action.get("reason") or "").strip()
            query_hint = str(action.get("query_hint") or "").strip()
            action_type = str(action.get("action_type") or "next_step").strip()
            if not label:
                continue
            normalized.append(
                {
                    "label": label,
                    "reason": reason or "A relevant next step was suggested from the current investigation context.",
                    "query_hint": query_hint or label,
                    "action_type": action_type,
                }
            )

        if not normalized:
            raise ValueError("No valid suggested actions were returned by the LLM.")

        return self._dedupe_actions(normalized)[:5]

    def _fallback_actions(self, *, state: dict[str, Any], response_contract: dict[str, Any]) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        citations = len(response_contract.get("citations", []))
        documents = len(response_contract.get("supporting_documents", []))
        risk_rating = str(response_contract.get("risk_rating") or "LOW").upper()
        evidence_count = len(response_contract.get("structured_evidence", []))
        topic = str(state.get("current_topic") or "the current investigation").strip()

        if citations > 0:
            actions.append(
                {
                    "label": "Show citations",
                    "reason": "The response already has citations that can be reviewed in more detail.",
                    "query_hint": "Show the citations",
                    "action_type": "citation_review",
                }
            )
        if documents > 0:
            actions.append(
                {
                    "label": "Open supporting document",
                    "reason": "Supporting documents are available for the current investigation.",
                    "query_hint": "Open the supporting document",
                    "action_type": "document_review",
                }
            )
        if evidence_count > 0:
            actions.append(
                {
                    "label": "Summarize findings",
                    "reason": "The current evidence can be condensed into an executive summary.",
                    "query_hint": "Summarize the findings",
                    "action_type": "summary",
                }
            )
        if risk_rating in {"HIGH", "CRITICAL"}:
            actions.append(
                {
                    "label": "Generate audit report",
                    "reason": f"The {topic} currently reflects elevated risk.",
                    "query_hint": "Generate an audit report",
                    "action_type": "report",
                }
            )
        if not actions:
            actions.extend(
                [
                    {
                        "label": "Ask another question",
                        "reason": "The current investigation can be refined with another audit question.",
                        "query_hint": "Ask another audit question",
                        "action_type": "follow_up",
                    },
                    {
                        "label": "Explain evidence",
                        "reason": "You can ask for a plain-language explanation of the evidence already returned.",
                        "query_hint": "Explain the evidence",
                        "action_type": "explain",
                    },
                    {
                        "label": "Compare vendors",
                        "reason": "If vendor activity exists, comparison can highlight relative risk.",
                        "query_hint": "Compare vendors",
                        "action_type": "comparison",
                    },
                ]
            )

        return self._dedupe_actions(actions)[:5]

    def _infer_topic(self, response_contract: dict[str, Any]) -> str:
        if response_contract.get("investigation_summary"):
            return str(response_contract.get("investigation_summary")).split(".")[0].strip()
        if response_contract.get("vendor_summary"):
            return "Vendor investigation"
        if response_contract.get("transaction_summary"):
            return "Transaction investigation"
        finding = response_contract.get("finding", {})
        if isinstance(finding, dict) and finding.get("finding_title"):
            return str(finding.get("finding_title"))
        intent = response_contract.get("intent", {})
        if isinstance(intent, dict) and intent.get("normalized_query"):
            return str(intent.get("normalized_query"))
        return str(response_contract.get("query") or "")

    def _infer_entities(self, response_contract: dict[str, Any]) -> dict[str, list[str]]:
        entities: dict[str, list[str]] = {"transactions": [], "vendors": [], "documents": [], "contracts": []}
        for row in response_contract.get("structured_evidence", []):
            if not isinstance(row, dict):
                continue
            transaction_id = row.get("transaction_id")
            vendor_id = row.get("vendor_id")
            contract_id = row.get("contract_id")
            if transaction_id:
                entities["transactions"].append(str(transaction_id))
            if vendor_id:
                entities["vendors"].append(str(vendor_id))
            if contract_id:
                entities["contracts"].append(str(contract_id))

        for document in response_contract.get("document_evidence", []):
            if not isinstance(document, dict):
                continue
            document_id = document.get("document_id")
            if document_id:
                entities["documents"].append(str(document_id))

        return {key: self._unique(values) for key, values in entities.items() if values}

    def _count_findings(self, response_contract: dict[str, Any]) -> int:
        key_findings = response_contract.get("key_findings", [])
        if isinstance(key_findings, list) and key_findings:
            return len(key_findings)
        finding = response_contract.get("finding", {})
        if isinstance(finding, dict) and (finding.get("finding_title") or finding.get("summary")):
            return 1
        return 0

    def _summarize_response(self, response_contract: dict[str, Any]) -> str:
        if response_contract.get("investigation_summary"):
            return str(response_contract.get("investigation_summary")).strip()
        finding = response_contract.get("finding", {})
        if isinstance(finding, dict) and finding.get("summary"):
            return str(finding.get("summary")).strip()
        return str(response_contract.get("final_response") or "").strip()

    def _snapshot_response(self, response_contract: dict[str, Any]) -> dict[str, Any]:
        fields = (
            "success",
            "query",
            "intent",
            "investigation_plan",
            "entities_investigated",
            "entity_type",
            "entity_id",
            "agents_used",
            "risk_rating",
            "risk_score",
            "risk_drivers",
            "document_intelligence_summary",
            "document_intelligence",
            "investigation_summary",
            "investigation_metrics",
            "top_supporting_evidence",
            "transaction_summary",
            "vendor_summary",
            "key_findings",
            "supporting_evidence",
            "supporting_documents",
            "citations",
            "navigation_payloads",
            "recommendations",
            "structured_evidence",
            "document_evidence",
            "sources",
            "reasoning",
            "finding",
            "final_response",
            "traceability",
            "evaluation",
            "execution_metadata",
            "suggested_actions",
            "conversation_state",
        )
        snapshot = {field: copy.deepcopy(response_contract.get(field)) for field in fields if field in response_contract}
        return snapshot

    def _save_state(self, state: dict[str, Any]) -> None:
        conversation_id = str(state.get("conversation_id") or "").strip()
        if not conversation_id:
            return
        with _STORE_LOCK:
            _CONVERSATION_STORE[conversation_id] = copy.deepcopy(state)

    def _new_state(self, conversation_id: str) -> dict[str, Any]:
        return {
            "conversation_id": conversation_id,
            "status": "NEW",
            "turn_count": 0,
            "current_topic": "",
            "recent_queries": [],
            "active_entities": {"transactions": [], "vendors": [], "documents": [], "contracts": []},
            "evidence_counts": {"structured": 0, "documents": 0, "citations": 0},
            "finding_count": 0,
            "last_query": "",
            "last_summary": "",
            "last_response_snapshot": {},
            "last_agents": [],
            "updated_at": self._timestamp(),
        }

    def _generate_conversation_id(self) -> str:
        return f"conv_{uuid.uuid4().hex[:12]}"

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _format_active_entities(self, active_entities: dict[str, Any]) -> str:
        parts: list[str] = []
        for label in ("transactions", "vendors", "documents", "contracts"):
            values = self._unique(active_entities.get(label, []))
            if values:
                parts.append(f"{label}: {', '.join(values[:5])}")
        return "; ".join(parts) if parts else "No previously selected entities"

    def _unique(self, values: list[Any]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            unique.append(text)
        return unique

    def _dedupe_actions(self, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for action in actions:
            label = str(action.get("label") or "").strip().lower()
            hint = str(action.get("query_hint") or "").strip().lower()
            signature = (label, hint)
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(action)
        return deduped

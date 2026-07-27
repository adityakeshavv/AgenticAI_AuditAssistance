from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.prompts.conversation_mode_prompt import build_conversation_mode_messages


_GREETING_KEYWORDS = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
}

_ABOUT_KEYWORDS = {
    "tell me about yourself",
    "who are you",
    "what can you do",
    "help me",
    "introduce yourself",
}

_COURTESY_KEYWORDS = {
    "thanks",
    "thank you",
    "got it",
    "okay",
    "ok",
    "great",
}

_OUT_OF_DOMAIN_KEYWORDS = {
    "weather",
    "joke",
    "news",
    "sports",
    "cricket",
    "movie",
    "music",
    "recipe",
    "pizza",
}

_AUDIT_KEYWORDS = {
    "audit",
    "transaction",
    "transactions",
    "vendor",
    "vendors",
    "supplier",
    "compliance",
    "approval",
    "approvals",
    "investigate",
    "investigation",
    "finding",
    "evidence",
    "risk",
    "flagged",
    "fraud",
    "policy",
    "policies",
    "document",
    "documents",
    "invoice",
    "expense",
    "claim",
    "threshold",
    "control",
    "controls",
    "governance",
    "workspace",
}

_AUDIT_DETAIL_HINTS = {
    "show",
    "list",
    "find",
    "review",
    "analyze",
    "analyse",
    "investigate",
    "summarize",
    "summarise",
    "search",
    "above",
    "below",
    "under",
    "over",
    "flagged",
    "risk",
    "high-risk",
    "high risk",
}

_VALID_MODES = {
    "greeting",
    "about",
    "conversation",
    "clarification",
    "upload_prompt",
    "source_search_prompt",
    "out_of_domain",
    "audit",
    "courtesy",
}


@dataclass(slots=True)
class ConversationModeResult:
    mode: str
    should_route_audit: bool
    assistant_message: str


class ConversationModeService:
    def classify(
        self,
        message: str,
        *,
        user_name: str | None = None,
        memory_context: dict[str, Any] | None = None,
    ) -> ConversationModeResult:
        text = self._normalize(message)
        first_name = self._first_name(user_name)
        has_recent_audit_context = bool(
            memory_context
            and (
                memory_context.get("active_investigation", {}).get("transaction_ids")
                or memory_context.get("active_investigation", {}).get("entity_ids")
                or memory_context.get("recent_turns")
            )
        )

        if self._contains_any(text, _GREETING_KEYWORDS):
            return ConversationModeResult(
                mode="greeting",
                should_route_audit=False,
                assistant_message=self._greeting_reply(first_name),
            )

        if self._contains_any(text, _ABOUT_KEYWORDS):
            return ConversationModeResult(
                mode="about",
                should_route_audit=False,
                assistant_message=self._about_reply(first_name),
            )

        if self._contains_any(text, _OUT_OF_DOMAIN_KEYWORDS):
            return ConversationModeResult(
                mode="out_of_domain",
                should_route_audit=False,
                assistant_message=self._out_of_domain_reply(first_name),
            )

        if self._is_upload_request(text):
            return ConversationModeResult(
                mode="upload_prompt",
                should_route_audit=False,
                assistant_message=self._upload_reply(first_name),
            )

        if self._is_source_search_request(text):
            return ConversationModeResult(
                mode="source_search_prompt",
                should_route_audit=False,
                assistant_message=self._source_search_reply(first_name),
            )

        if get_settings().openai_api_key:
            try:
                llm_result = self._llm_classify(
                    message=message,
                    user_name=user_name,
                    memory_context=memory_context or {},
                )
                if llm_result.mode == "audit" and self._needs_clarification(text, has_recent_audit_context):
                    return ConversationModeResult(
                        mode="clarification",
                        should_route_audit=False,
                        assistant_message=self._clarify_reply(text, first_name),
                    )
                return llm_result
            except Exception:
                pass

        if self._is_audit_request(text, has_recent_audit_context):
            if self._needs_clarification(text, has_recent_audit_context):
                return ConversationModeResult(
                    mode="clarification",
                    should_route_audit=False,
                    assistant_message=self._clarify_reply(text, first_name),
                )
            return ConversationModeResult(
                mode="audit",
                should_route_audit=True,
                assistant_message="",
            )

        if self._contains_any(text, _COURTESY_KEYWORDS):
            return ConversationModeResult(
                mode="courtesy",
                should_route_audit=False,
                assistant_message=self._courtesy_reply(first_name),
            )

        return ConversationModeResult(
            mode="conversation",
            should_route_audit=False,
            assistant_message=self._conversation_reply(first_name),
        )

    def _llm_classify(
        self,
        *,
        message: str,
        user_name: str | None,
        memory_context: dict[str, Any],
    ) -> ConversationModeResult:
        settings = get_settings()
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed. Run pip install -r backend/requirements.txt.") from exc

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.25,
            messages=build_conversation_mode_messages(
                message=message,
                user_name=user_name,
                memory_context=memory_context,
            ),
        )
        content = (response.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        payload = json.loads(content)
        mode = str(payload.get("mode", "conversation")).strip()
        should_route_audit = bool(payload.get("should_route_audit", False))
        assistant_message = str(payload.get("assistant_message", "")).strip()

        if mode not in _VALID_MODES:
            raise ValueError(f"Invalid conversation mode returned by LLM: {mode}")

        if mode == "audit":
            return ConversationModeResult(mode="audit", should_route_audit=True, assistant_message="")

        if not assistant_message:
            assistant_message = self._conversation_reply(self._first_name(user_name))

        if mode == "clarification":
            should_route_audit = False

        return ConversationModeResult(
            mode=mode,
            should_route_audit=should_route_audit and mode != "clarification",
            assistant_message=assistant_message,
        )

    @staticmethod
    def _normalize(message: str) -> str:
        return " ".join(message.lower().strip().split())

    @staticmethod
    def _first_name(user_name: str | None) -> str | None:
        if not user_name:
            return None
        clean = user_name.strip()
        if not clean:
            return None
        return clean.split()[0]

    @staticmethod
    def _contains_any(text: str, terms: set[str]) -> bool:
        return any(term in text for term in terms)

    def _is_audit_request(self, text: str, has_recent_audit_context: bool) -> bool:
        if has_recent_audit_context and len(text.split()) <= 10:
            return True
        if self._contains_any(text, _AUDIT_KEYWORDS):
            return True
        if self._contains_any(text, _AUDIT_DETAIL_HINTS) and self._contains_any(
            text,
            {"transaction", "vendor", "compliance", "approval", "investigation", "policy", "policies", "governance"},
        ):
            return True
        return False

    def _needs_clarification(self, text: str, has_recent_audit_context: bool) -> bool:
        if not self._contains_any(text, {"transaction", "vendor", "compliance", "approval", "investigation", "policy", "policies", "governance"}):
            return False
        if "investigate vendor" in text and any(token.startswith("vnd") for token in text.replace("-", " ").split()):
            return False
        if "investigate transaction" in text and any(token.startswith("txn") for token in text.replace("-", " ").split()):
            return False
        if self._contains_any(text, {"show flagged", "high-risk", "high risk", "above", "below", "under", "over", "threshold"}):
            return False
        if has_recent_audit_context and len(text.split()) <= 5:
            return False
        vague_audit_starts = {"review", "analyze", "analyse", "investigate", "check", "inspect", "look"}
        if text.split() and text.split()[0] in vague_audit_starts:
            return True
        if any(term in text for term in ("starting with policies", "starting with policy", "policy review", "policy work", "policy checks")):
            return True
        return self._contains_any(text, {"certain transactions", "certain vendors", "some transactions", "some vendors"})

    def _greeting_reply(self, first_name: str | None) -> str:
        if first_name:
            return f"Hi {first_name}, I'm here and ready whenever you are. What would you like to look into today?"
        return "Hi, I'm here and ready whenever you are. What would you like to look into today?"

    def _about_reply(self, first_name: str | None) -> str:
        lead = f"Nice to meet you, {first_name}." if first_name else "Nice to meet you."
        return (
            f"{lead} I'm your audit copilot. I can help you review transactions, vendors, evidence, "
            "policies, approvals, documents, and investigations. If you want, we can start with a question, "
            "an uploaded document, or a connected source."
        )

    def _out_of_domain_reply(self, first_name: str | None) -> str:
        prefix = f"{first_name}, " if first_name else ""
        return (
            f"{prefix}I'm sorry, I can't help with that request. I'm designed for audit work such as "
            "transaction review, evidence tracing, policy checks, and investigation support. "
            "If you'd like, we can switch back to an audit question right away."
        )

    def _courtesy_reply(self, first_name: str | None) -> str:
        if first_name:
            return f"You're welcome, {first_name}. What would you like to look at next?"
        return "You're welcome. What would you like to look at next?"

    def _conversation_reply(self, first_name: str | None) -> str:
        if first_name:
            return f"I'm here for you, {first_name}. Whenever you're ready, we can jump into an audit question."
        return "I'm here for you. Whenever you're ready, we can jump into an audit question."

    def _upload_reply(self, first_name: str | None) -> str:
        prefix = f"{first_name}, " if first_name else ""
        return (
            f"{prefix}sure - go ahead and upload the document here. Once it's attached, I'll read it and guide you on the next step."
        )

    def _source_search_reply(self, first_name: str | None) -> str:
        prefix = f"{first_name}, " if first_name else ""
        return (
            f"{prefix}great - I can search the connected sources for you. Please share the transaction ID, vendor ID, threshold, "
            "or control area you want me to review."
        )

    def _clarify_reply(self, text: str, first_name: str | None) -> str:
        prefix = f"{first_name}, " if first_name else ""
        if "vendor" in text:
            return (
                f"{prefix}do you want me to review a specific vendor ID, or should I search the connected sources for vendor activity and supporting evidence?"
            )
        if "policy" in text or "policies" in text or "governance" in text:
            return (
                f"{prefix}are you looking for a specific policy, a control area, or a set of documents related to policy review?"
            )
        if "transaction" in text:
            return (
                f"{prefix}would you like to upload supporting documents, or should I search the connected sources for the transaction details?"
            )
        if "approval" in text:
            return (
                f"{prefix}should I inspect approval exceptions in the connected sources, or do you want to upload supporting evidence first?"
            )
        return (
            f"{prefix}I can help with that. Would you like to upload supporting documents, or should I search the connected sources for the evidence first?"
        )

    @staticmethod
    def _is_upload_request(text: str) -> bool:
        upload_phrases = {
            "upload",
            "attach",
            "attach document",
            "attach documents",
            "upload document",
            "upload documents",
            "upload file",
            "upload files",
        }
        return text in upload_phrases or text.startswith("upload ")

    @staticmethod
    def _is_source_search_request(text: str) -> bool:
        search_phrases = {
            "search",
            "search sources",
            "search the sources",
            "search provided sources",
            "search through provided sources",
            "look it up",
        }
        return text in search_phrases or ("search" in text and "source" in text)

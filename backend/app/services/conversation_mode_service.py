from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.prompts.conversation_mode_prompt import build_conversation_mode_messages


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
        memory_context = memory_context or {}

        if get_settings().openai_api_key:
            try:
                result = self._llm_classify(
                    message=message,
                    user_name=user_name,
                    memory_context=memory_context,
                )
                if result.mode == "audit" and self._is_fragment(text):
                    return ConversationModeResult(
                        mode="clarification",
                        should_route_audit=False,
                        assistant_message=self._fragment_reply(first_name),
                    )
                return result
            except Exception:
                pass

        if self._is_fragment(text):
            return ConversationModeResult(
                mode="clarification",
                should_route_audit=False,
                assistant_message=self._fragment_reply(first_name),
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
            temperature=0.35,
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
        mode = str(payload.get("mode", "conversation")).strip() or "conversation"
        if mode not in _VALID_MODES:
            mode = "conversation"

        should_route_audit = bool(payload.get("should_route_audit", False))
        assistant_message = str(payload.get("assistant_message", "")).strip()

        if mode == "audit":
            return ConversationModeResult(mode="audit", should_route_audit=True, assistant_message="")

        if not assistant_message:
            assistant_message = self._default_message(mode, user_name)

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
    def _is_fragment(text: str) -> bool:
        stripped = text.strip()
        if len(stripped) < 3:
            return True
        tokens = stripped.split()
        if len(tokens) == 1 and len(stripped) <= 2:
            return True
        if len(tokens) == 1 and stripped.isalpha() and len(stripped) <= 3:
            return True
        return False

    def _default_message(self, mode: str, user_name: str | None) -> str:
        first_name = self._first_name(user_name)
        if mode == "greeting":
            return self._greeting_reply(first_name)
        if mode == "about":
            return self._about_reply(first_name)
        if mode == "out_of_domain":
            return self._out_of_domain_reply(first_name)
        if mode == "upload_prompt":
            return self._upload_reply(first_name)
        if mode == "source_search_prompt":
            return self._source_search_reply(first_name)
        if mode == "courtesy":
            return self._courtesy_reply(first_name)
        if mode == "clarification":
            return self._fragment_reply(first_name)
        return self._conversation_reply(first_name)

    def _greeting_reply(self, first_name: str | None) -> str:
        if first_name:
            return f"Hi {first_name}, I’m here and ready whenever you are. What would you like to look into today?"
        return "Hi, I’m here and ready whenever you are. What would you like to look into today?"

    def _about_reply(self, first_name: str | None) -> str:
        lead = f"Nice to meet you, {first_name}." if first_name else "Nice to meet you."
        return (
            f"{lead} I’m your audit copilot. I can help you review transactions, vendors, evidence, "
            "policies, approvals, documents, and investigations. If you want, we can start with a question, "
            "an uploaded document, or a connected source."
        )

    def _out_of_domain_reply(self, first_name: str | None) -> str:
        prefix = f"{first_name}, " if first_name else ""
        return (
            f"{prefix}I’m sorry, I can’t help with that request. I’m designed for audit work such as "
            "transaction review, evidence tracing, policy checks, and investigation support. "
            "If you’d like, we can switch back to an audit question right away."
        )

    def _courtesy_reply(self, first_name: str | None) -> str:
        if first_name:
            return f"You’re welcome, {first_name}. What would you like to look at next?"
        return "You’re welcome. What would you like to look at next?"

    def _conversation_reply(self, first_name: str | None) -> str:
        if first_name:
            return (
                f"Absolutely, {first_name} — we can take it from here. "
                "Would you like to start with transactions, vendors, policies, a document upload, or a connected source?"
            )
        return (
            "Absolutely — we can take it from here. "
            "Would you like to start with transactions, vendors, policies, a document upload, or a connected source?"
        )

    def _fragment_reply(self, first_name: str | None) -> str:
        prefix = f"{first_name}, " if first_name else ""
        return (
            f"{prefix}I’m not quite sure what you mean yet. Could you add a little more detail, "
            "or tell me which transaction, vendor, policy, or document you want me to look at?"
        )

    def _upload_reply(self, first_name: str | None) -> str:
        prefix = f"{first_name}, " if first_name else ""
        return f"{prefix}sure - go ahead and upload the document here. Once it’s attached, I’ll read it and guide you on the next step."

    def _source_search_reply(self, first_name: str | None) -> str:
        prefix = f"{first_name}, " if first_name else ""
        return (
            f"{prefix}great - I can search the connected sources for you. Please share the transaction ID, vendor ID, threshold, "
            "or control area you want me to review."
        )


__all__ = ["ConversationModeService", "ConversationModeResult"]

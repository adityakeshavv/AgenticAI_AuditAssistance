from __future__ import annotations

import json
from typing import Any


def build_conversation_context_messages(
    *,
    query: str,
    session_context: dict[str, Any] | None,
) -> list[dict[str, str]]:
    payload = {
        "query": query,
        "session_context": session_context or {},
    }

    system = (
        "You are a conversation context resolver for an enterprise audit copilot.\n"
        "Your job is to decide whether the current user message depends on prior conversation context, and if so, rewrite it "
        "into a fully self-contained message with explicit entities and topic references.\n"
        "You must behave like a thoughtful conversational assistant, not a keyword matcher.\n"
        "Use the conversation history, active investigation state, prior entities, prior documents, and source mode to infer meaning.\n"
        "If the message is a follow-up, set is_followup to true and produce a resolved_query that can stand on its own.\n"
        "If the message is not a follow-up, keep resolved_query equal to the original query.\n"
        "If the user is being vague but still clearly referring to the ongoing conversation, preserve that context in resolved_query.\n"
        "If the message is too short, fragmentary, or ambiguous, set is_followup according to context and provide the most helpful rewrite you can.\n"
        "Return JSON only with this exact shape:\n"
        "{\n"
        '  \"is_followup\": true,\n'
        '  \"resolved_query\": \"...\",\n'
        '  \"injected_context\": {\n'
        '    \"entity_type\": \"...\",\n'
        '    \"entity_ids\": [\"...\"],\n'
        '    \"transaction_ids\": [\"...\"],\n'
        '    \"document_ids\": [\"...\"],\n'
        '    \"topics\": [\"...\"],\n'
        '    \"source_modes\": [\"...\"],\n'
        '    \"reason\": \"...\"\n'
        "  }\n"
        "}\n"
        "Do not mention that you are rewriting the query. Do not add explanation outside JSON."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, indent=2, default=str)},
    ]

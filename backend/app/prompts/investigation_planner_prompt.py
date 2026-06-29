from __future__ import annotations

import json
from typing import Any


def build_investigation_planner_messages(
    *,
    query: str,
    intent: dict[str, Any],
    available_agents: list[dict[str, str]],
    investigation_context: dict[str, Any],
) -> list[dict[str, str]]:

    # Extract conversation context for the prompt
    conv_ctx = investigation_context.get("conversation_context", {})
    recent_turns = conv_ctx.get("recent_turns", [])
    active_inv = conv_ctx.get("active_investigation", {})
    long_term_facts = conv_ctx.get("long_term_facts", [])
    turn_count = conv_ctx.get("turn_count", 0)

    # Build conversation history section
    history_section = ""
    if recent_turns:
        lines = []
        for t in recent_turns[-4:]:
            lines.append(f"  User: {t['user']}")
            lines.append(f"  Assistant: {t['summary']}")
            if t.get("risk"):
                lines.append(f"  Risk: {t['risk']}")
        history_section = "Conversation history (most recent first):\n" + "\n".join(lines)

    # Build active investigation section
    inv_section = ""
    if active_inv.get("status") == "in_progress":
        inv_section = (
            f"Active investigation context:\n"
            f"  Entity type: {active_inv.get('entity_type', 'unknown')}\n"
            f"  Entities: {active_inv.get('entity_ids', [])}\n"
            f"  Transactions reviewed: {active_inv.get('transaction_count', 0)}\n"
            f"  Risk rating so far: {active_inv.get('risk_rating', 'unknown')}\n"
            f"  Topics: {active_inv.get('topics', [])}\n"
            f"  Prior key findings: {long_term_facts[:3]}"
        )

    payload = {
        "query": query,
        "intent": intent,
        "available_agents": available_agents,
        "investigation_context": {
            k: v for k, v in investigation_context.items()
            if k != "conversation_context"
        },
        "turn_count": turn_count,
    }

    system = f"""
You are the investigation planner for an enterprise AI Audit Copilot.
Your responsibility is to convert a user audit question into a minimal, evidence-first execution plan.

This is a CONVERSATIONAL audit system. The user may ask follow-up questions.
Use the conversation history and active investigation to avoid redundant re-queries.

You must decide:
- which agents should participate
- in what order they should execute
- why each agent is required
- what output each agent should produce

Planning rules:
- If this is a follow-up about already-retrieved entities, prefer document_retrieval_agent or compliance_agent over re-running transaction_agent.
- Use evidence-first ordering so downstream agents consume earlier outputs.
- Include transaction_agent before document_retrieval_agent when fresh transaction evidence is needed.
- Include vendor_investigation_agent only when vendor-level follow-up adds clear value.
- Keep the plan minimal — do not add agents that are not needed.
- Do not generate SQL. Do not invent facts. Do not write prose outside the JSON schema.
- If the query cannot be mapped to a supported investigation scenario, return an unsupported plan.

{history_section}

{inv_section}

Available agents will be supplied in the input. Use only those agents.

Return JSON only with this exact schema:
{{
  "investigation_type": "short scenario label",
  "entities_required": ["entity", "entity"],
  "agents_required": ["agent_name", "agent_name"],
  "reasoning": ["why this plan is needed"],
  "plan": [
    {{
      "agent": "transaction_agent",
      "reason": "Retrieve matching transactions.",
      "expected_output": "Structured transaction evidence",
      "query_hint": "Optional sub-query or execution hint"
    }}
  ]
}}

Do not include markdown, code fences, or extra keys.
""".strip()

    user = json.dumps(payload, indent=2, default=str)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.services.conversation_memory_service import ConversationMemoryService


class ConversationMemorySearchService:
    STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "about",
        "show",
        "tell",
        "what",
        "where",
        "when",
        "why",
        "how",
        "list",
        "find",
        "need",
        "please",
        "can",
        "could",
        "would",
        "should",
        "you",
        "your",
        "they",
        "them",
        "those",
        "these",
        "same",
        "previous",
        "prior",
        "follow",
        "followup",
        "follow-up",
    }

    def search(
        self,
        *,
        query: str,
        session_id: str,
        top_k: int = 5,
        memory_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = ConversationMemoryService.get_session(session_id)
        if not session:
            return {
                "memory_evidence": [],
                "memory_sources": [],
                "memory_summary": "",
                "memory_matches": 0,
            }

        query_tokens = self._tokenize(query)
        recent_turns = list(session.get("session", {}).get("turns", []))
        if not recent_turns:
            return {
                "memory_evidence": [],
                "memory_sources": [],
                "memory_summary": "",
                "memory_matches": 0,
            }

        scored: list[tuple[float, dict[str, Any]]] = []
        follow_up_hint = self._looks_like_follow_up(query)
        total_turns = len(recent_turns)
        for index, turn in enumerate(recent_turns):
            haystack = " ".join(
                str(turn.get(field) or "")
                for field in (
                    "user",
                    "assistant_summary",
                    "assistant_message",
                    "finding_title",
                    "finding_summary",
                    "recommendation",
                    "transaction_summary",
                    "vendor_summary",
                    "investigation_summary",
                )
            ).lower()
            turn_tokens = self._tokenize(haystack)
            overlap = query_tokens.intersection(turn_tokens)
            score = float(len(overlap))

            if follow_up_hint:
                score += 1.5

            recency_boost = (index + 1) / max(total_turns, 1)
            score += recency_boost

            if query_tokens and any(token in haystack for token in query_tokens):
                score += 1.0

            if score <= 0:
                continue

            evidence = self._build_memory_evidence(turn, query=query, score=score, overlap=overlap)
            scored.append((score, evidence))

        scored.sort(key=lambda item: (-item[0], str(item[1].get("timestamp") or "")))
        selected = [item for _, item in scored[:top_k]]

        memory_sources: list[str] = []
        if selected:
            memory_sources.append("conversation_memory")

        memory_summary = self._build_summary(selected, query=query)
        return {
            "memory_evidence": selected,
            "memory_sources": memory_sources,
            "memory_summary": memory_summary,
            "memory_matches": len(selected),
        }

    def _build_memory_evidence(self, turn: dict[str, Any], *, query: str, score: float, overlap: set[str]) -> dict[str, Any]:
        assistant_summary = str(turn.get("assistant_summary") or "").strip()
        assistant_message = str(turn.get("assistant_message") or "").strip()
        snippet = assistant_summary or assistant_message or "Conversation turn"
        if len(snippet) > 260:
            snippet = snippet[:260].rsplit(" ", 1)[0].strip() + "..."

        return {
            "source_type": "conversation_memory",
            "session_id": turn.get("session_id"),
            "turn_id": turn.get("turn_id"),
            "timestamp": turn.get("timestamp"),
            "user": turn.get("user"),
            "assistant_summary": assistant_summary,
            "assistant_message": assistant_message[:400],
            "conversation_mode": turn.get("conversation_mode"),
            "entity_type": turn.get("entity_type"),
            "entity_id": turn.get("entity_id"),
            "risk_rating": turn.get("risk_rating"),
            "document_ids": list(turn.get("document_ids", [])),
            "structured_evidence_count": turn.get("structured_evidence_count", 0),
            "document_evidence_count": turn.get("document_evidence_count", 0),
            "citations_count": turn.get("citations_count", 0),
            "relevance_score": round(min(score / 8.0, 1.0), 3),
            "snippet": snippet,
            "reason_selected": self._reason_selected(query=query, turn=turn, overlap=overlap),
        }

    def _build_summary(self, evidence: list[dict[str, Any]], *, query: str) -> str:
        if not evidence:
            return ""
        parts = []
        first = evidence[0]
        if first.get("assistant_summary"):
            parts.append(first["assistant_summary"])
        elif first.get("snippet"):
            parts.append(first["snippet"])
        if len(evidence) > 1:
            parts.append(f"{len(evidence)} related conversation turn(s) matched the query.")
        if query.strip():
            parts.append(f"Query context: {query.strip()[:80]}.")
        return " ".join(parts)

    def _reason_selected(self, *, query: str, turn: dict[str, Any], overlap: set[str]) -> str:
        if not overlap:
            return "Relevant conversation turn matched by recency and follow-up context."
        matched = ", ".join(sorted(overlap)[:5])
        return f"Conversation turn matched query terms: {matched}."

    def _tokenize(self, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", text.lower())
            if token not in self.STOPWORDS
        }

    def _looks_like_follow_up(self, query: str) -> bool:
        lowered = query.lower()
        hints = (
            "this",
            "that",
            "those",
            "these",
            "same",
            "why",
            "how",
            "what about",
            "and then",
            "continue",
            "follow up",
            "follow-up",
            "them",
            "it",
        )
        return any(hint in lowered for hint in hints)

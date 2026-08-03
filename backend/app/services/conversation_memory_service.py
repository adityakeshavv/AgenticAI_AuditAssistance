"""
ConversationMemoryService
=========================
Manages four memory layers for the Audit Copilot:
  - short_term   : last N messages (sliding window)
  - session      : full conversation history for this session
  - investigation: accumulated evidence, findings, entities for the active investigation
  - long_term    : distilled key facts (lightweight, in-process; no vector DB required)
"""
from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


_MAX_SHORT_TERM = 10   # message pairs kept in sliding window
_MAX_LONG_TERM  = 40   # distilled facts kept


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationMemoryService:
    """Thread-safe (within a single process) in-memory conversation store keyed by session_id."""

    # Class-level store shared across requests — suitable for single-worker dev/staging.
    # Replace with Redis / DB backend for multi-worker production.
    _sessions: dict[str, dict[str, Any]] = {}

    # ── Public API ──────────────────────────────────────────────────────────

    @classmethod
    def create_session(cls) -> str:
        session_id = str(uuid.uuid4())
        cls._sessions[session_id] = cls._empty_session(session_id)
        return session_id

    @classmethod
    def get_or_create(cls, session_id: str | None) -> tuple[str, dict[str, Any]]:
        """Return (session_id, session_state). Creates if missing."""
        if session_id and session_id in cls._sessions:
            return session_id, cls._sessions[session_id]
        sid = cls.create_session()
        return sid, cls._sessions[sid]

    @classmethod
    def get_session(cls, session_id: str) -> dict[str, Any] | None:
        return cls._sessions.get(session_id)

    @classmethod
    def bootstrap_from_history(cls, session_id: str, turns: list[dict[str, Any]]) -> None:
        if session_id not in cls._sessions:
            cls._sessions[session_id] = cls._empty_session(session_id)

        session = cls._sessions[session_id]
        session["short_term"] = []
        session["session"]["turns"] = []
        session["investigation"] = cls._empty_session(session_id)["investigation"]
        session["long_term"] = {"facts": []}

        for turn in turns:
            session["session"]["turns"].append(turn)
            session["short_term"].append(turn)
            if len(session["short_term"]) > _MAX_SHORT_TERM:
                session["short_term"] = session["short_term"][-_MAX_SHORT_TERM:]

            assistant_response = turn.get("assistant_response") or {}
            cls._update_investigation(session["investigation"], assistant_response, turn)
            cls._update_long_term(session["long_term"], turn)

        session["last_updated"] = _now()

    @classmethod
    def add_turn(
        cls,
        session_id: str,
        *,
        user_message: str,
        assistant_response: dict[str, Any],
    ) -> None:
        session = cls._sessions.get(session_id)
        if not session:
            return

        turn = {
            "turn_id": str(uuid.uuid4()),
            "timestamp": _now(),
            "user": user_message,
            "assistant_summary": cls._summarize_response(assistant_response),
            "assistant_message": assistant_response.get("assistant_message", assistant_response.get("final_response", "")),
            "conversation_mode": assistant_response.get("conversation_mode", "audit"),
            "source_route": deepcopy(assistant_response.get("source_route", {})),
            "source_mode": (assistant_response.get("source_route", {}) or {}).get("source_mode"),
            "document_ids": cls._collect_document_ids(assistant_response),
            "risk_rating": assistant_response.get("risk_rating"),
            "key_findings": list(assistant_response.get("key_findings", [])),
            "entities_investigated": list(assistant_response.get("entities_investigated", [])),
            "entity_type": assistant_response.get("entity_type"),
            "entity_id": assistant_response.get("entity_id"),
            "structured_evidence_count": len(assistant_response.get("structured_evidence", [])),
            "document_evidence_count": len(assistant_response.get("document_evidence", [])),
            "citations_count": len(assistant_response.get("citations", [])),
            "agents_used": list(assistant_response.get("agents_used", [])),
            "transaction_summary": assistant_response.get("transaction_summary", ""),
            "vendor_summary": assistant_response.get("vendor_summary", ""),
            "investigation_summary": assistant_response.get("investigation_summary", ""),
            "finding_title": assistant_response.get("finding", {}).get("title", ""),
            "finding_summary": assistant_response.get("finding", {}).get("summary", ""),
            "recommendation": assistant_response.get("finding", {}).get("recommendation", ""),
            "assistant_response": deepcopy(assistant_response),
        }

        # session memory — full history
        session["session"]["turns"].append(turn)

        # short-term — sliding window
        session["short_term"].append(turn)
        if len(session["short_term"]) > _MAX_SHORT_TERM:
            session["short_term"] = session["short_term"][-_MAX_SHORT_TERM:]

        # investigation memory — merge evidence
        cls._update_investigation(session["investigation"], assistant_response, turn)

        # long-term — distilled facts
        cls._update_long_term(session["long_term"], turn)

        session["last_updated"] = _now()

    @classmethod
    def get_context_for_planner(cls, session_id: str) -> dict[str, Any]:
        """Compact context dict supplied to the investigation planner."""
        session = cls._sessions.get(session_id)
        if not session:
            return {}

        short = session["short_term"]
        inv = session["investigation"]
        lt = session["long_term"]

        return {
            "recent_turns": [
                {
                    "user": t["user"],
                    "summary": t["assistant_summary"],
                    "risk": t["risk_rating"],
                    "source_mode": t.get("source_mode"),
                    "source_route": deepcopy(t.get("source_route", {})),
                    "document_ids": list(t.get("document_ids", [])),
                }
                for t in short[-6:]
            ],
            "active_investigation": {
                "entity_type": inv.get("entity_type"),
                "entity_ids": list(inv.get("entity_ids", set())),
                "transaction_ids": list(inv.get("transaction_ids", set())),
                "topics": list(inv.get("topics", [])),
                "risk_rating": inv.get("risk_rating"),
                "transaction_count": inv.get("transaction_count", 0),
                "document_count": inv.get("document_count", 0),
                "finding_count": inv.get("finding_count", 0),
                "status": inv.get("status", "in_progress"),
                "source_modes": inv.get("source_modes", []),
                "document_ids": list(inv.get("document_ids", set())),
            },
            "long_term_facts": lt["facts"][-20:],
            "turn_count": len(session["session"]["turns"]),
        }

    @classmethod
    def get_investigation_state(cls, session_id: str) -> dict[str, Any]:
        session = cls._sessions.get(session_id)
        if not session:
            return {}
        return deepcopy(session["investigation"])

    @classmethod
    def list_sessions(cls) -> list[str]:
        return list(cls._sessions.keys())

    # ── Private helpers ─────────────────────────────────────────────────────

    @classmethod
    def _empty_session(cls, session_id: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "created_at": _now(),
            "last_updated": _now(),
            "short_term": [],
            "session": {"turns": []},
            "investigation": {
                "entity_type": None,
                "entity_ids": set(),
                "transaction_ids": set(),
                "document_ids": set(),
                "topics": [],
                "source_modes": [],
                "risk_rating": None,
                "transaction_count": 0,
                "document_count": 0,
                "finding_count": 0,
                "key_findings": [],
                "recommendations": [],
                "status": "idle",
            },
            "long_term": {"facts": []},
        }

    @classmethod
    def _summarize_response(cls, r: dict[str, Any]) -> str:
        parts = []
        if r.get("investigation_summary"):
            parts.append(r["investigation_summary"])
        elif r.get("transaction_summary"):
            parts.append(r["transaction_summary"])
        elif r.get("vendor_summary"):
            parts.append(r["vendor_summary"])
        elif r.get("finding", {}).get("summary"):
            parts.append(r["finding"]["summary"])
        elif r.get("final_response"):
            parts.append(str(r["final_response"])[:400])
        elif r.get("assistant_message"):
            parts.append(str(r["assistant_message"])[:400])
        risk = r.get("risk_rating")
        if risk:
            parts.append(f"Risk: {risk}.")
        n_ev = len(r.get("structured_evidence", [])) + len(r.get("document_evidence", []))
        if n_ev:
            parts.append(f"{n_ev} evidence item(s).")
        return " ".join(parts) or "No summary available."

    @classmethod
    def _update_investigation(
        cls,
        inv: dict[str, Any],
        r: dict[str, Any],
        turn: dict[str, Any],
    ) -> None:
        inv["status"] = "in_progress"

        if r.get("entity_type") and not inv["entity_type"]:
            inv["entity_type"] = r["entity_type"]

        # accumulate entity IDs
        for eid in r.get("entities_investigated", []):
            inv["entity_ids"].add(str(eid))
        if r.get("entity_id"):
            inv["entity_ids"].add(str(r["entity_id"]))

        # accumulate transaction IDs from structured evidence
        for ev in r.get("structured_evidence", []):
            tid = ev.get("transaction_id")
            if tid:
                inv["transaction_ids"].add(str(tid))

        # accumulate document IDs from document evidence
        for ev in r.get("document_evidence", []):
            did = ev.get("document_id")
            if did:
                inv["document_ids"].add(str(did))

        # counts
        inv["transaction_count"] = max(inv["transaction_count"], len(r.get("structured_evidence", [])))
        inv["document_count"] += len(r.get("document_evidence", []))

        # risk
        rr = r.get("risk_rating")
        if rr in ("HIGH", "CRITICAL"):
            inv["risk_rating"] = rr
        elif rr == "MEDIUM" and inv["risk_rating"] not in ("HIGH", "CRITICAL"):
            inv["risk_rating"] = rr
        elif not inv["risk_rating"]:
            inv["risk_rating"] = rr or "LOW"

        # findings
        for f in turn["key_findings"]:
            if f and f not in inv["key_findings"]:
                inv["key_findings"].append(f)
        if turn.get("recommendation") and turn["recommendation"] not in inv["recommendations"]:
            inv["recommendations"].append(turn["recommendation"])
        if turn["key_findings"]:
            inv["finding_count"] += 1

        # topics
        q_lower = turn["user"].lower()
        for kw in ("vendor", "transaction", "compliance", "approval", "policy", "fraud", "flagged", "risk"):
            if kw in q_lower and kw not in inv["topics"]:
                inv["topics"].append(kw)

        # source modes
        source_mode = str(r.get("source_route", {}).get("source_mode") or "").strip().lower()
        if source_mode and source_mode not in inv["source_modes"]:
            inv["source_modes"].append(source_mode)

    @classmethod
    def _update_long_term(cls, lt: dict[str, Any], turn: dict[str, Any]) -> None:
        facts = lt["facts"]
        for f in turn["key_findings"]:
            if f and f not in facts:
                facts.append(f)
        if turn["finding_summary"] and turn["finding_summary"] not in facts:
            facts.append(turn["finding_summary"])
        source_mode = turn.get("source_mode")
        if source_mode:
            source_fact = f"Source route used: {source_mode}"
            if source_fact not in facts:
                facts.append(source_fact)
        if len(facts) > _MAX_LONG_TERM:
            lt["facts"] = facts[-_MAX_LONG_TERM:]

    @staticmethod
    def _collect_document_ids(r: dict[str, Any]) -> list[str]:
        ids: list[str] = []
        for item in r.get("document_evidence", []) or []:
            did = item.get("document_id")
            if did:
                value = str(did)
                if value not in ids:
                    ids.append(value)
        for item in r.get("citations", []) or []:
            did = item.get("document_id")
            if did:
                value = str(did)
                if value not in ids:
                    ids.append(value)
        for item in r.get("supporting_documents", []) or []:
            did = item.get("document_id")
            if did:
                value = str(did)
                if value not in ids:
                    ids.append(value)
        return ids

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.crud import governance_audit_crud, user_crud
from app.models.governance_audit import GovernanceAuditLog
from app.services.realtime_service import publish_realtime_event


logger = logging.getLogger(__name__)


class GovernanceAuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record_router_decision(
        self,
        *,
        actor_user_id: str | None = None,
        actor_name: str | None = None,
        query: str,
        routing_decision: dict[str, Any],
        selected_agents: list[str] | None = None,
        workspace_id: str | None = None,
        connection_id: str | None = None,
        severity: str = "info",
    ) -> GovernanceAuditLog | None:
        selected_agents = selected_agents or []
        agent = str(routing_decision.get("agent") or "general_agent")
        confidence = routing_decision.get("confidence")
        reason = str(routing_decision.get("reason") or "").strip() or "Routing decision recorded."
        escalate = bool(routing_decision.get("escalate_to_planner"))
        candidate_agents = list(routing_decision.get("candidate_agents") or [])
        summary = (
            f"Router selected {agent} for query '{query[:120]}'. "
            f"Escalate to planner: {'yes' if escalate else 'no'}."
        )
        return self.record_event(
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            action_type="router_decision_reviewed",
            entity_type="audit_query",
            entity_id=agent,
            workspace_id=workspace_id,
            connection_id=connection_id,
            severity=severity,
            summary=summary,
            before_state={
                "query": query,
                "candidate_agents": candidate_agents,
            },
            after_state={
                "selected_agent": agent,
                "selected_agents": selected_agents,
                "confidence": confidence,
                "reason": reason,
                "escalate_to_planner": escalate,
                "decision_source": routing_decision.get("decision_source"),
                "candidate_agents": candidate_agents,
            },
        )

    def record_event(
        self,
        *,
        actor_user_id: str | None = None,
        action_type: str,
        entity_type: str,
        summary: str,
        entity_id: str | None = None,
        workspace_id: str | None = None,
        connection_id: str | None = None,
        severity: str = "info",
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        actor_name: str | None = None,
    ) -> GovernanceAuditLog | None:
        try:
            resolved_actor_name = actor_name or self._resolve_actor_name(actor_user_id)
            event = governance_audit_crud.create_audit_event(
                self.db,
                actor_user_id=actor_user_id,
                actor_name=resolved_actor_name,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=entity_id,
                workspace_id=workspace_id,
                connection_id=connection_id,
                severity=severity,
                summary=summary,
                before_state=before_state,
                after_state=after_state,
            )
            if event is not None:
                publish_realtime_event(
                    {
                        "type": "governance_event",
                        "audit_log_id": event.audit_log_id,
                        "action_type": event.action_type,
                        "entity_type": event.entity_type,
                        "entity_id": event.entity_id,
                        "workspace_id": event.workspace_id,
                        "connection_id": event.connection_id,
                        "severity": event.severity,
                        "summary": event.summary,
                        "actor_user_id": event.actor_user_id,
                        "actor_name": event.actor_name,
                        "created_at": event.created_at.isoformat() if event.created_at else None,
                    }
                )
            return event
        except Exception as exc:  # pragma: no cover - audit logging must never block primary actions
            logger.debug("Governance audit event was not recorded: %s", exc)
            return None

    def list_events(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        action_type: str | None = None,
        entity_type: str | None = None,
        severity: str | None = None,
        actor_user_id: str | None = None,
        entity_id: str | None = None,
        workspace_id: str | None = None,
        connection_id: str | None = None,
        search: str | None = None,
    ) -> list[GovernanceAuditLog]:
        return governance_audit_crud.list_audit_events(
            self.db,
            limit=limit,
            offset=offset,
            action_type=action_type,
            entity_type=entity_type,
            severity=severity,
            actor_user_id=actor_user_id,
            entity_id=entity_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
            search=search,
        )

    def summarize_router_reviews(
        self,
        *,
        limit: int = 200,
        offset: int = 0,
        severity: str | None = None,
        actor_user_id: str | None = None,
        workspace_id: str | None = None,
        connection_id: str | None = None,
    ) -> dict[str, Any]:
        decision_events = self.list_events(
            limit=limit,
            offset=offset,
            action_type="router_decision_reviewed",
            entity_type="audit_query",
            severity=severity,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        path_events = self.list_events(
            limit=limit,
            offset=offset,
            action_type="router_path_reviewed",
            entity_type="audit_query",
            severity=severity,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
        )

        all_events = list(decision_events) + list(path_events)
        all_events.sort(key=lambda event: event.created_at or datetime.min.replace(tzinfo=None), reverse=True)

        selected_agent_counts: Counter[str] = Counter()
        candidate_agent_counts: Counter[str] = Counter()
        decision_source_counts: Counter[str] = Counter()
        escalated_count = 0
        low_confidence_count = 0
        path_mismatch_count = 0

        decision_items: list[dict[str, Any]] = []
        path_items: list[dict[str, Any]] = []

        for event in decision_events:
            after_state = event.after_state or {}
            selected_agent = str(after_state.get("selected_agent") or event.entity_id or "general_agent")
            confidence = float(after_state.get("confidence") or 0)
            selected_agent_counts[selected_agent] += 1
            for candidate in after_state.get("candidate_agents") or []:
                if candidate:
                    candidate_agent_counts[str(candidate)] += 1
            decision_source_counts[str(after_state.get("decision_source") or "unknown")] += 1
            if after_state.get("escalate_to_planner"):
                escalated_count += 1
            if confidence < 0.75:
                low_confidence_count += 1
            decision_items.append(
                {
                    "audit_log_id": event.audit_log_id,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                    "query": (event.before_state or {}).get("query"),
                    "selected_agent": selected_agent,
                    "confidence": confidence,
                    "escalate_to_planner": bool(after_state.get("escalate_to_planner")),
                    "decision_source": after_state.get("decision_source"),
                    "candidate_agents": list(after_state.get("candidate_agents") or []),
                    "severity": event.severity,
                    "summary": event.summary,
                }
            )

        for event in path_events:
            after_state = event.after_state or {}
            selected_agent = str(after_state.get("selected_agent") or "")
            selected_agents = list(after_state.get("selected_agents") or [])
            if selected_agent and selected_agents and selected_agent not in selected_agents:
                path_mismatch_count += 1
            path_items.append(
                {
                    "audit_log_id": event.audit_log_id,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                    "query": (event.after_state or {}).get("query") or (event.before_state or {}).get("query"),
                    "selected_agent": selected_agent,
                    "selected_agents": selected_agents,
                    "routing_decision": (event.after_state or {}).get("routing_decision"),
                    "severity": event.severity,
                    "summary": event.summary,
                }
            )

        total_reviews = len(decision_events) + len(path_events)
        top_selected_agents = [
            {"agent": agent, "count": count}
            for agent, count in selected_agent_counts.most_common(10)
        ]
        top_candidate_agents = [
            {"agent": agent, "count": count}
            for agent, count in candidate_agent_counts.most_common(10)
        ]
        recent_misroutes = [
            item
            for item in path_items[:20]
            if item.get("selected_agent") and item.get("selected_agents") and item["selected_agent"] not in item["selected_agents"]
        ]

        return {
            "total_reviews": total_reviews,
            "decision_events": len(decision_events),
            "path_review_events": len(path_events),
            "escalated_count": escalated_count,
            "low_confidence_count": low_confidence_count,
            "path_mismatch_count": path_mismatch_count,
            "decision_source_counts": dict(decision_source_counts),
            "top_selected_agents": top_selected_agents,
            "top_candidate_agents": top_candidate_agents,
            "recent_misroutes": recent_misroutes,
            "recent_decisions": decision_items[:20],
            "recent_path_reviews": path_items[:20],
        }

    def serialize_event(self, event: GovernanceAuditLog) -> dict[str, Any]:
        return {
            "audit_log_id": event.audit_log_id,
            "actor_user_id": event.actor_user_id,
            "actor_name": event.actor_name,
            "action_type": event.action_type,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "workspace_id": event.workspace_id,
            "connection_id": event.connection_id,
            "severity": event.severity,
            "summary": event.summary,
            "before_state": event.before_state,
            "after_state": event.after_state,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }

    def _resolve_actor_name(self, actor_user_id: str | None) -> str | None:
        if not actor_user_id:
            return None
        user = user_crud.get_user_by_id(self.db, actor_user_id)
        if user is None:
            return None
        return user.full_name or user.email

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud import database_connection_crud, monitoring_alert_crud, transaction_crud
from app.services.governance_audit_service import GovernanceAuditService
from app.services.realtime_service import publish_realtime_event
from app.services.workspace_service import WorkspaceService
from app.database import SessionLocal


logger = logging.getLogger(__name__)


class MonitoringService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def scan_now(self) -> dict[str, Any]:
        observed_fingerprints: set[str] = set()
        self._scan_connection_health(observed_fingerprints)
        self._scan_workspace_health(observed_fingerprints)
        self._scan_transaction_risk(observed_fingerprints)

        monitoring_alert_crud.resolve_missing_alerts(self.db, active_fingerprints=observed_fingerprints)
        self.db.commit()

        summary = self.build_summary()
        publish_realtime_event(
            {
                "type": "monitoring_alerts_updated",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": summary,
            }
        )
        return summary

    def build_summary(self) -> dict[str, Any]:
        summary = monitoring_alert_crud.summarize_alerts(self.db)
        summary["scan_interval_seconds"] = int(self.settings.monitoring_scan_interval_seconds)
        return summary

    def list_alerts(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        severity: str | None = None,
        alert_type: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        alerts = monitoring_alert_crud.list_alerts(
            self.db,
            limit=limit,
            offset=offset,
            status=status,
            severity=severity,
            alert_type=alert_type,
            search=search,
        )
        return [self.serialize_alert(alert) for alert in alerts]

    def update_alert_status(self, *, alert_id: str, status: str, actor_user_id: str | None = None) -> dict[str, Any] | None:
        alert = monitoring_alert_crud.update_alert_status(self.db, alert_id=alert_id, status=status, actor_user_id=actor_user_id)
        if alert is None:
            return None
        self.db.commit()
        publish_realtime_event(
            {
                "type": "monitoring_alert_status_updated",
                "alert_id": alert.alert_id,
                "status": alert.status,
                "severity": alert.severity,
                "title": alert.title,
            }
        )
        return self.serialize_alert(alert)

    def serialize_alert(self, alert) -> dict[str, Any]:
        return {
            "alert_id": alert.alert_id,
            "fingerprint": alert.fingerprint,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "status": alert.status,
            "title": alert.title,
            "summary": alert.summary,
            "source_type": alert.source_type,
            "source_id": alert.source_id,
            "owner_user_id": alert.owner_user_id,
            "workspace_id": alert.workspace_id,
            "connection_id": alert.connection_id,
            "metric_value": alert.metric_value,
            "details": alert.details,
            "acknowledged_by": alert.acknowledged_by,
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "resolved_by": alert.resolved_by,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "updated_at": alert.updated_at.isoformat() if alert.updated_at else None,
        }

    def _scan_connection_health(self, observed_fingerprints: set[str]) -> int:
        created = 0
        connections = database_connection_crud.list_all_connections(self.db)
        for connection in connections:
            if connection.last_test_status == "passed" and connection.is_active:
                continue

            fingerprint = f"connection-health:{connection.connection_id}"
            observed_fingerprints.add(fingerprint)
            severity = "critical" if not connection.is_active else "warning"
            summary = (
                f"Connection '{connection.connection_name}' needs attention. "
                f"Last test status: {connection.last_test_status or 'not tested'}."
            )
            details = {
                "connection_name": connection.connection_name,
                "database_type": connection.database_type,
                "host": connection.host,
                "database_name": connection.database_name,
                "last_test_status": connection.last_test_status,
                "last_test_message": connection.last_test_message,
                "is_active": connection.is_active,
            }
            alert, was_created = monitoring_alert_crud.upsert_alert(
                self.db,
                fingerprint=fingerprint,
                alert_type="connection_health",
                severity=severity,
                title="Database connection needs attention",
                summary=summary,
                source_type="database_connection",
                source_id=connection.connection_id,
                owner_user_id=connection.owner_user_id,
                connection_id=connection.connection_id,
                details=details,
            )
            if was_created:
                created += 1
                GovernanceAuditService(self.db).record_event(
                    actor_user_id=None,
                    action_type="monitoring_alert_created",
                    entity_type="database_connection",
                    entity_id=connection.connection_id,
                    connection_id=connection.connection_id,
                    severity=severity,
                    summary=summary,
                    after_state=details,
                )
            else:
                logger.debug("Monitoring alert refreshed for connection %s", alert.connection_id)
        return created

    def _scan_workspace_health(self, observed_fingerprints: set[str]) -> int:
        created = 0
        try:
            workspaces = WorkspaceService(self.db).list_all_workspaces()
        except Exception as exc:  # pragma: no cover - workspace access should not block monitoring
            logger.debug("Workspace monitoring skipped: %s", exc)
            return 0

        for workspace in workspaces:
            if not workspace.get("is_active", True):
                continue
            selected_connections = list(workspace.get("selected_connection_ids") or [])
            active_connection_id = workspace.get("active_connection_id")
            fingerprint = f"workspace-health:{workspace.get('workspace_id')}"
            if selected_connections and active_connection_id:
                continue

            observed_fingerprints.add(fingerprint)
            severity = "warning"
            summary = (
                f"Workspace '{workspace.get('workspace_name')}' is not fully linked to an active source."
            )
            details = {
                "workspace_name": workspace.get("workspace_name"),
                "selected_connection_ids": selected_connections,
                "active_connection_id": active_connection_id,
                "is_active": workspace.get("is_active"),
            }
            _, was_created = monitoring_alert_crud.upsert_alert(
                self.db,
                fingerprint=fingerprint,
                alert_type="workspace_configuration",
                severity=severity,
                title="Workspace needs source configuration",
                summary=summary,
                source_type="audit_workspace",
                source_id=workspace.get("workspace_id"),
                owner_user_id=workspace.get("owner_user_id"),
                workspace_id=workspace.get("workspace_id"),
                details=details,
            )
            if was_created:
                created += 1
        return created

    def _scan_transaction_risk(self, observed_fingerprints: set[str]) -> int:
        created = 0
        flagged_rows, flagged_total = transaction_crud.get_flagged_transactions(
            self.db,
            page=1,
            page_size=min(self.settings.max_page_size, 25),
        )
        high_risk_rows, high_risk_total = transaction_crud.get_high_risk_transactions(
            self.db,
            page=1,
            page_size=min(self.settings.max_page_size, 25),
        )

        if flagged_total >= self.settings.monitoring_flagged_transaction_threshold:
            fingerprint = "transaction-risk:flagged"
            observed_fingerprints.add(fingerprint)
            summary = (
                f"{flagged_total} flagged transaction(s) are currently open for review."
            )
            details = {
                "flagged_total": flagged_total,
                "flagged_preview": [row.transaction_id for row in flagged_rows[:5]],
                "threshold": self.settings.monitoring_flagged_transaction_threshold,
            }
            _, was_created = monitoring_alert_crud.upsert_alert(
                self.db,
                fingerprint=fingerprint,
                alert_type="transaction_risk_spike",
                severity="warning" if flagged_total < self.settings.monitoring_high_risk_transaction_threshold else "critical",
                title="Flagged transactions exceed monitoring threshold",
                summary=summary,
                source_type="transaction_master",
                source_id="flagged_transactions",
                metric_value=flagged_total,
                details=details,
            )
            if was_created:
                created += 1

        if high_risk_total >= self.settings.monitoring_high_risk_transaction_threshold:
            fingerprint = "transaction-risk:high-risk"
            observed_fingerprints.add(fingerprint)
            summary = f"{high_risk_total} high-risk transaction(s) were detected in the latest scan."
            details = {
                "high_risk_total": high_risk_total,
                "high_risk_preview": [row.transaction_id for row in high_risk_rows[:5]],
                "threshold": self.settings.monitoring_high_risk_transaction_threshold,
            }
            _, was_created = monitoring_alert_crud.upsert_alert(
                self.db,
                fingerprint=fingerprint,
                alert_type="transaction_risk_spike",
                severity="critical" if high_risk_total > self.settings.monitoring_high_risk_transaction_threshold * 2 else "warning",
                title="High-risk transaction activity detected",
                summary=summary,
                source_type="transaction_master",
                source_id="high_risk_transactions",
                metric_value=high_risk_total,
                details=details,
            )
            if was_created:
                created += 1
        return created


class MonitoringSupervisor:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._running = False
        self.settings = get_settings()

    async def ensure_started(self) -> None:
        if not self.settings.monitoring_enabled:
            return
        async with self._lock:
            if self._task and not self._task.done():
                return
            self._stop_event = asyncio.Event()
            self._running = True
            self._task = asyncio.create_task(self._loop())

    async def shutdown(self) -> None:
        async with self._lock:
            self._running = False
            self._stop_event.set()
            task = self._task
            self._task = None
        if task and not task.done():
            try:
                await asyncio.wait_for(task, timeout=3)
            except (asyncio.CancelledError, TimeoutError, Exception):
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=1)
                except Exception:
                    pass

    async def _loop(self) -> None:
        if not self.settings.monitoring_enabled:
            return
        interval = max(30, int(self.settings.monitoring_scan_interval_seconds))
        while self._running and not self._stop_event.is_set():
            try:
                self._scan_once()
            except Exception as exc:  # pragma: no cover - monitoring should not stop the app
                logger.debug("Monitoring scan failed: %s", exc, exc_info=True)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    def _scan_once(self) -> None:
        with SessionLocal() as db:
            service = MonitoringService(db)
            service.scan_now()


monitoring_supervisor = MonitoringSupervisor()

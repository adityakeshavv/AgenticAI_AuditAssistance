from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Select, desc, or_, select
from sqlalchemy.orm import Session

from app.models.monitoring_alert import MonitoringAlert


def _base_statement() -> Select[tuple[MonitoringAlert]]:
    return select(MonitoringAlert)


def upsert_alert(
    db: Session,
    *,
    fingerprint: str,
    alert_type: str,
    severity: str,
    title: str,
    summary: str,
    source_type: str,
    source_id: str | None = None,
    owner_user_id: str | None = None,
    workspace_id: str | None = None,
    connection_id: str | None = None,
    metric_value: int | None = None,
    details: dict[str, Any] | None = None,
) -> tuple[MonitoringAlert, bool]:
    now = datetime.now(timezone.utc)
    alert = db.scalar(select(MonitoringAlert).where(MonitoringAlert.fingerprint == fingerprint))
    created = False

    if alert is None:
        alert = MonitoringAlert(
            alert_id=uuid4().hex,
            fingerprint=fingerprint,
            alert_type=alert_type,
            severity=severity,
            status="open",
            title=title,
            summary=summary,
            source_type=source_type,
            source_id=source_id,
            owner_user_id=owner_user_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
            metric_value=metric_value,
            details=details,
            created_at=now,
            updated_at=now,
        )
        created = True
    else:
        alert.alert_type = alert_type
        alert.severity = severity
        alert.status = "open"
        alert.title = title
        alert.summary = summary
        alert.source_type = source_type
        alert.source_id = source_id
        alert.owner_user_id = owner_user_id
        alert.workspace_id = workspace_id
        alert.connection_id = connection_id
        alert.metric_value = metric_value
        alert.details = details
        alert.updated_at = now
        alert.acknowledged_at = None if alert.status == "open" else alert.acknowledged_at
        alert.resolved_at = None
        alert.resolved_by = None
        alert.acknowledged_by = None if alert.status == "open" else alert.acknowledged_by

    db.add(alert)
    db.flush()
    return alert, created


def list_alerts(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    search: str | None = None,
) -> list[MonitoringAlert]:
    statement = _base_statement()
    if status:
        statement = statement.where(MonitoringAlert.status == status)
    if severity:
        statement = statement.where(MonitoringAlert.severity == severity)
    if alert_type:
        statement = statement.where(MonitoringAlert.alert_type == alert_type)
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                MonitoringAlert.title.ilike(term),
                MonitoringAlert.summary.ilike(term),
                MonitoringAlert.source_type.ilike(term),
            )
        )
    statement = statement.order_by(desc(MonitoringAlert.updated_at), desc(MonitoringAlert.created_at))
    statement = statement.offset(max(0, offset)).limit(max(1, limit))
    return list(db.scalars(statement).all())


def list_open_alerts(db: Session) -> list[MonitoringAlert]:
    statement = (
        _base_statement()
        .where(MonitoringAlert.status.in_(["open", "acknowledged"]))
        .order_by(desc(MonitoringAlert.severity), desc(MonitoringAlert.updated_at))
    )
    return list(db.scalars(statement).all())


def resolve_missing_alerts(db: Session, *, active_fingerprints: set[str]) -> int:
    changed = 0
    now = datetime.now(timezone.utc)
    for alert in list_open_alerts(db):
        if alert.fingerprint in active_fingerprints:
            continue
        alert.status = "resolved"
        alert.resolved_at = now
        alert.updated_at = now
        db.add(alert)
        changed += 1
    if changed:
        db.flush()
    return changed


def update_alert_status(
    db: Session,
    *,
    alert_id: str,
    status: str,
    actor_user_id: str | None = None,
) -> MonitoringAlert | None:
    alert = db.scalar(select(MonitoringAlert).where(MonitoringAlert.alert_id == alert_id))
    if alert is None:
        return None

    now = datetime.now(timezone.utc)
    alert.status = status
    alert.updated_at = now
    if status == "acknowledged":
        alert.acknowledged_at = now
        alert.acknowledged_by = actor_user_id
        alert.resolved_at = None
        alert.resolved_by = None
    elif status == "resolved":
        alert.resolved_at = now
        alert.resolved_by = actor_user_id
    db.add(alert)
    db.flush()
    return alert


def summarize_alerts(db: Session) -> dict[str, Any]:
    alerts = list(db.scalars(_base_statement().order_by(desc(MonitoringAlert.updated_at)).limit(200)).all())
    total_alerts = len(alerts)
    open_alerts = sum(1 for alert in alerts if alert.status in {"open", "acknowledged"})
    critical_alerts = sum(1 for alert in alerts if alert.severity == "critical" and alert.status in {"open", "acknowledged"})
    warning_alerts = sum(1 for alert in alerts if alert.severity == "warning" and alert.status in {"open", "acknowledged"})
    info_alerts = sum(1 for alert in alerts if alert.severity == "info" and alert.status in {"open", "acknowledged"})
    connection_alerts = sum(1 for alert in alerts if alert.source_type == "database_connection" and alert.status in {"open", "acknowledged"})
    transaction_alerts = sum(1 for alert in alerts if alert.source_type == "transaction_master" and alert.status in {"open", "acknowledged"})
    workspace_alerts = sum(1 for alert in alerts if alert.source_type == "audit_workspace" and alert.status in {"open", "acknowledged"})
    last_scan_at = max((alert.updated_at for alert in alerts if alert.updated_at is not None), default=None)
    recent_alerts = alerts[:10]

    return {
        "total_alerts": total_alerts,
        "open_alerts": open_alerts,
        "critical_alerts": critical_alerts,
        "warning_alerts": warning_alerts,
        "info_alerts": info_alerts,
        "connection_alerts": connection_alerts,
        "transaction_alerts": transaction_alerts,
        "workspace_alerts": workspace_alerts,
        "last_scan_at": last_scan_at.isoformat() if last_scan_at else None,
        "recent_alerts": recent_alerts,
    }

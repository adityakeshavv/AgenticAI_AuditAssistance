from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud import user_crud
from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.schemas.audit import RouterReviewSummaryResponse
from app.schemas.auth import AuthUser, UserStatusUpdate
from app.schemas.monitoring import MonitoringAlertStatusUpdate, MonitoringScanResponse, MonitoringSummaryResponse
from app.services.auth_service import AuthService
from app.services.database_connector_service import DatabaseConnectorService
from app.services.governance_audit_service import GovernanceAuditService
from app.services.monitoring_service import MonitoringService
from app.services.realtime_service import realtime_hub
from app.services.workspace_service import WorkspaceService


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _current_user: AuthUser = Depends(require_admin),
) -> dict:
    auth_service = AuthService(db)
    users = [auth_service.serialize_user(user) for user in user_crud.list_users(db)]
    return {"users": [user.model_dump() for user in users]}


@router.get("/connections")
def list_connections(
    db: Session = Depends(get_db),
    _current_user: AuthUser = Depends(require_admin),
) -> dict:
    svc = DatabaseConnectorService(db)
    return {"connections": svc.list_all_connections()}


@router.get("/workspaces")
def list_workspaces(
    db: Session = Depends(get_db),
    _current_user: AuthUser = Depends(require_admin),
) -> dict:
    svc = WorkspaceService(db)
    return {"workspaces": svc.list_all_workspaces()}


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_admin),
) -> dict:
    if user_id == current_user.user_id and payload.is_active is False:
        GovernanceAuditService(db).record_event(
            actor_user_id=current_user.user_id,
            actor_name=current_user.full_name or current_user.email,
            action_type="admin_self_deactivation_blocked",
            entity_type="user",
            entity_id=user_id,
            severity="warning",
            summary="An admin attempted to deactivate their own account and was blocked.",
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own admin account.")
    user = user_crud.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user_crud.set_user_active_status(db, user, is_active=payload.is_active)
    GovernanceAuditService(db).record_event(
        actor_user_id=current_user.user_id,
        actor_name=current_user.full_name or current_user.email,
        action_type="user_status_updated",
        entity_type="user",
        entity_id=user.user_id,
        severity="info",
        summary=f"User '{user.full_name or user.email}' status changed to {'active' if payload.is_active else 'inactive'}.",
        before_state={"is_active": not payload.is_active},
        after_state={"is_active": payload.is_active},
    )
    db.commit()
    auth_service = AuthService(db)
    return {"success": True, "user": auth_service.serialize_user(user)}


@router.get("/audit-events")
def list_audit_events(
    limit: int = 50,
    offset: int = 0,
    action_type: str | None = None,
    entity_type: str | None = None,
    severity: str | None = None,
    search: str | None = None,
    actor_user_id: str | None = None,
    entity_id: str | None = None,
    workspace_id: str | None = None,
    connection_id: str | None = None,
    db: Session = Depends(get_db),
    _current_user: AuthUser = Depends(require_admin),
) -> dict:
    svc = GovernanceAuditService(db)
    events = [
        svc.serialize_event(event)
        for event in svc.list_events(
            limit=limit,
            offset=offset,
            action_type=action_type,
            entity_type=entity_type,
            severity=severity,
            search=search,
            actor_user_id=actor_user_id,
            entity_id=entity_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
    ]
    return {"events": events}


@router.get("/router-summary", response_model=RouterReviewSummaryResponse)
def router_summary(
    limit: int = 200,
    offset: int = 0,
    severity: str | None = None,
    actor_user_id: str | None = None,
    workspace_id: str | None = None,
    connection_id: str | None = None,
    db: Session = Depends(get_db),
    _current_user: AuthUser = Depends(require_admin),
) -> RouterReviewSummaryResponse:
    svc = GovernanceAuditService(db)
    summary = svc.summarize_router_reviews(
        limit=limit,
        offset=offset,
        severity=severity,
        actor_user_id=actor_user_id,
        workspace_id=workspace_id,
        connection_id=connection_id,
    )
    return RouterReviewSummaryResponse(
        total_reviews=summary["total_reviews"],
        decision_events=summary["decision_events"],
        path_review_events=summary["path_review_events"],
        escalated_count=summary["escalated_count"],
        low_confidence_count=summary["low_confidence_count"],
        path_mismatch_count=summary["path_mismatch_count"],
        decision_source_counts=summary["decision_source_counts"],
        top_selected_agents=summary["top_selected_agents"],
        top_candidate_agents=summary["top_candidate_agents"],
        recent_misroutes=summary["recent_misroutes"],
        recent_decisions=summary["recent_decisions"],
        recent_path_reviews=summary["recent_path_reviews"],
    )


@router.get("/active-users")
def active_users(
    _current_user: AuthUser = Depends(require_admin),
) -> dict:
    active_users = realtime_hub.list_active_users()
    return {"active_users": active_users, "active_user_count": len(active_users)}


@router.get("/monitoring/summary", response_model=MonitoringSummaryResponse)
def monitoring_summary(
    db: Session = Depends(get_db),
    _current_user: AuthUser = Depends(require_admin),
) -> MonitoringSummaryResponse:
    svc = MonitoringService(db)
    summary = svc.build_summary()
    return MonitoringSummaryResponse(**summary)


@router.get("/monitoring/alerts")
def monitoring_alerts(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    _current_user: AuthUser = Depends(require_admin),
) -> dict:
    svc = MonitoringService(db)
    return {
        "alerts": svc.list_alerts(
            limit=limit,
            offset=offset,
            status=status,
            severity=severity,
            alert_type=alert_type,
            search=search,
        )
    }


@router.post("/monitoring/scan", response_model=MonitoringScanResponse)
def monitoring_scan(
    db: Session = Depends(get_db),
    _current_user: AuthUser = Depends(require_admin),
) -> MonitoringScanResponse:
    svc = MonitoringService(db)
    summary = svc.scan_now()
    return MonitoringScanResponse(summary=MonitoringSummaryResponse(**summary))


@router.patch("/monitoring/alerts/{alert_id}")
def update_monitoring_alert(
    alert_id: str,
    payload: MonitoringAlertStatusUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_admin),
) -> dict:
    svc = MonitoringService(db)
    updated = svc.update_alert_status(alert_id=alert_id, status=payload.status, actor_user_id=current_user.user_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    return {"success": True, "alert": updated}

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MonitoringAlertRecord(BaseModel):
    alert_id: str
    fingerprint: str
    alert_type: str
    severity: str
    status: str
    title: str
    summary: str
    source_type: str
    source_id: str | None = None
    owner_user_id: str | None = None
    workspace_id: str | None = None
    connection_id: str | None = None
    metric_value: int | None = None
    details: dict[str, Any] | None = None
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MonitoringSummaryResponse(BaseModel):
    total_alerts: int
    open_alerts: int
    critical_alerts: int
    warning_alerts: int
    info_alerts: int
    connection_alerts: int
    transaction_alerts: int
    workspace_alerts: int
    last_scan_at: datetime | None = None
    scan_interval_seconds: int = Field(default=120)
    recent_alerts: list[MonitoringAlertRecord] = Field(default_factory=list)


class MonitoringAlertStatusUpdate(BaseModel):
    status: str


class MonitoringScanResponse(BaseModel):
    success: bool = True
    summary: MonitoringSummaryResponse

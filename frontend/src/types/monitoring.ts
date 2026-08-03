export interface MonitoringAlertRecord {
  alert_id: string;
  fingerprint: string;
  alert_type: string;
  severity: string;
  status: string;
  title: string;
  summary: string;
  source_type: string;
  source_id?: string | null;
  owner_user_id?: string | null;
  workspace_id?: string | null;
  connection_id?: string | null;
  metric_value?: number | null;
  details?: Record<string, unknown> | null;
  acknowledged_by?: string | null;
  acknowledged_at?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MonitoringSummaryResponse {
  total_alerts: number;
  open_alerts: number;
  critical_alerts: number;
  warning_alerts: number;
  info_alerts: number;
  connection_alerts: number;
  transaction_alerts: number;
  workspace_alerts: number;
  last_scan_at?: string | null;
  scan_interval_seconds: number;
  recent_alerts: MonitoringAlertRecord[];
}

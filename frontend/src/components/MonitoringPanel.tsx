import { useEffect, useMemo, useState } from 'react';
import { getMonitoringSummary, listMonitoringAlerts, runMonitoringScan, updateMonitoringAlertStatus } from '../services/adminApi';
import type { MonitoringAlertRecord, MonitoringSummaryResponse } from '../types/monitoring';

interface MonitoringPanelProps {
  isAdmin: boolean;
  realtimeTick?: number;
}

function timeAgo(value?: string | null): string {
  if (!value) return 'n/a';
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return value;
  const diffMinutes = Math.max(0, Math.round((Date.now() - timestamp) / 60000));
  if (diffMinutes < 1) return 'just now';
  if (diffMinutes < 60) return `${diffMinutes} min ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} hr ago`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
}

function titleCase(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function severityTone(value: string): string {
  const normalized = value.toLowerCase();
  if (normalized === 'critical') return 'background: rgba(239, 68, 68, 0.14); color: #b91c1c; border-color: rgba(239, 68, 68, 0.28);';
  if (normalized === 'warning') return 'background: rgba(245, 158, 11, 0.14); color: #b45309; border-color: rgba(245, 158, 11, 0.28);';
  if (normalized === 'info') return 'background: rgba(59, 130, 246, 0.12); color: #1d4ed8; border-color: rgba(59, 130, 246, 0.24);';
  return 'background: rgba(16, 185, 129, 0.12); color: #047857; border-color: rgba(16, 185, 129, 0.24);';
}

function statusTone(value: string): string {
  const normalized = value.toLowerCase();
  if (normalized === 'resolved') return 'background: rgba(16, 185, 129, 0.12); color: #047857; border-color: rgba(16, 185, 129, 0.2);';
  if (normalized === 'acknowledged') return 'background: rgba(59, 130, 246, 0.12); color: #1d4ed8; border-color: rgba(59, 130, 246, 0.2);';
  return 'background: rgba(148, 163, 184, 0.12); color: #475569; border-color: rgba(148, 163, 184, 0.2);';
}

function SectionMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="card-sm">
      <p className="label" style={{ marginBottom: '0.35rem' }}>{label}</p>
      <p style={{ fontSize: '1.55rem', fontWeight: 800, marginBottom: '0.25rem' }}>{value}</p>
      <p className="small-copy">{detail}</p>
    </div>
  );
}

export function MonitoringPanel({ isAdmin, realtimeTick = 0 }: MonitoringPanelProps) {
  const [summary, setSummary] = useState<MonitoringSummaryResponse | null>(null);
  const [alerts, setAlerts] = useState<MonitoringAlertRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningScan, setRunningScan] = useState(false);
  const [savingAlertId, setSavingAlertId] = useState<string | null>(null);

  const refresh = async () => {
    if (!isAdmin) return;
    setLoading(true);
    setError(null);
    try {
      const [summaryResponse, alertResponse] = await Promise.all([
        getMonitoringSummary(),
        listMonitoringAlerts({ limit: 25 }),
      ]);
      setSummary(summaryResponse);
      setAlerts(alertResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load monitoring data.');
      setSummary(null);
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [isAdmin, realtimeTick]);

  const metrics = useMemo(() => [
    { label: 'Open Alerts', value: String(summary?.open_alerts ?? 0), detail: 'Alerts currently requiring attention.' },
    { label: 'Critical', value: String(summary?.critical_alerts ?? 0), detail: 'Escalated issues detected by monitoring.' },
    { label: 'Connection Alerts', value: String(summary?.connection_alerts ?? 0), detail: 'Saved sources that need validation.' },
    { label: 'Risk Alerts', value: String(summary?.transaction_alerts ?? 0), detail: 'Flagged or high-risk transaction activity.' },
  ], [summary]);

  const handleRunScan = async () => {
    setRunningScan(true);
    setError(null);
    try {
      const summaryResponse = await runMonitoringScan();
      setSummary(summaryResponse);
      const alertResponse = await listMonitoringAlerts({ limit: 25 });
      setAlerts(alertResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to run monitoring scan.');
    } finally {
      setRunningScan(false);
    }
  };

  const handleUpdateStatus = async (alertId: string, status: string) => {
    setSavingAlertId(alertId);
    setError(null);
    try {
      const updated = await updateMonitoringAlertStatus(alertId, status);
      setAlerts((current) => current.map((item) => (item.alert_id === updated.alert_id ? updated : item)));
      const summaryResponse = await getMonitoringSummary();
      setSummary(summaryResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update alert status.');
    } finally {
      setSavingAlertId(null);
    }
  };

  if (!isAdmin) {
    return (
      <div className="card">
        <p className="label" style={{ marginBottom: '0.45rem' }}>Monitoring</p>
        <p className="body-copy">Monitoring alerts are available to admin users only.</p>
      </div>
    );
  }

  return (
    <div className="stack" style={{ gap: '1rem' }}>
      <div className="dashboard-hero" style={{ alignItems: 'center' }}>
        <div>
          <p className="eyebrow" style={{ marginBottom: '0.35rem' }}>Monitoring</p>
          <h1 style={{ fontSize: '1.7rem', fontWeight: 800, marginBottom: '0.35rem' }}>Continuous Monitoring & Alerts</h1>
          <p className="body-copy" style={{ maxWidth: '70ch' }}>
            Track connection health, transaction risk spikes, and workspace readiness from a single executive view.
          </p>
        </div>
        <button className="btn btn-primary" type="button" onClick={handleRunScan} disabled={runningScan}>
          {runningScan ? 'Scanning...' : 'Run Scan Now'}
        </button>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'rgba(239, 68, 68, 0.35)' }}>
          <p className="label" style={{ marginBottom: '0.35rem' }}>Monitoring Error</p>
          <p className="body-copy">{error}</p>
        </div>
      )}

      <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))' }}>
        {metrics.map((metric) => (
          <SectionMetric key={metric.label} {...metric} />
        ))}
      </div>

      <div className="card">
        <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.85rem' }}>
          <div>
            <p className="label" style={{ marginBottom: '0.3rem' }}>Latest Scan</p>
            <p className="body-copy">
              {summary?.last_scan_at ? `Completed ${timeAgo(summary.last_scan_at)}` : 'No scan recorded yet.'}
            </p>
          </div>
          <div className="flex-row" style={{ gap: '0.5rem', flexWrap: 'wrap' }}>
            <span className="source-pill">Interval: {summary?.scan_interval_seconds ?? 120}s</span>
            <span className="badge badge-completed">Realtime enabled</span>
          </div>
        </div>
        {loading ? (
          <p className="small-copy">Loading monitoring alerts...</p>
        ) : alerts.length === 0 ? (
          <div className="card-sm">
            <strong>No active alerts</strong>
            <p className="small-copy" style={{ marginTop: '0.35rem' }}>
              The environment is currently stable. Continuous scans will keep watching for connection and risk issues.
            </p>
          </div>
        ) : (
          <div className="stack-sm">
            {alerts.map((alert) => (
              <div key={alert.alert_id} className="card-sm">
                <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                  <div>
                    <p className="label" style={{ marginBottom: '0.35rem' }}>{titleCase(alert.alert_type)}</p>
                    <strong style={{ fontSize: '1.04rem' }}>{alert.title}</strong>
                  </div>
                  <div className="flex-row" style={{ gap: '0.45rem', flexWrap: 'wrap' }}>
                    <span className="source-pill" style={{ border: '1px solid transparent', ...parseInlineStyle(severityTone(alert.severity)) }}>
                      {titleCase(alert.severity)}
                    </span>
                    <span className="source-pill" style={{ border: '1px solid transparent', ...parseInlineStyle(statusTone(alert.status)) }}>
                      {titleCase(alert.status)}
                    </span>
                  </div>
                </div>
                <p className="body-copy" style={{ marginTop: '0.55rem' }}>{alert.summary}</p>
                <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', marginTop: '0.75rem' }}>
                  <MiniField label="Source" value={titleCase(alert.source_type)} />
                  <MiniField label="Metric" value={alert.metric_value != null ? String(alert.metric_value) : '—'} />
                  <MiniField label="Updated" value={timeAgo(alert.updated_at)} />
                </div>
                {alert.details && Object.keys(alert.details).length > 0 && (
                  <details style={{ marginTop: '0.75rem' }}>
                    <summary className="small-copy" style={{ cursor: 'pointer' }}>View details</summary>
                    <pre style={{ marginTop: '0.5rem', whiteSpace: 'pre-wrap', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                      {JSON.stringify(alert.details, null, 2)}
                    </pre>
                  </details>
                )}
                <div className="flex-row" style={{ gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.75rem' }}>
                  {alert.status !== 'acknowledged' && (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleUpdateStatus(alert.alert_id, 'acknowledged')}
                      disabled={savingAlertId === alert.alert_id}
                    >
                      Acknowledge
                    </button>
                  )}
                  {alert.status !== 'resolved' && (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleUpdateStatus(alert.alert_id, 'resolved')}
                      disabled={savingAlertId === alert.alert_id}
                    >
                      Resolve
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MiniField({ label, value }: { label: string; value: string }) {
  return (
    <div className="card-sm">
      <p className="label" style={{ marginBottom: '0.25rem' }}>{label}</p>
      <p className="small-copy">{value}</p>
    </div>
  );
}

function parseInlineStyle(styleString: string): Record<string, string> {
  return styleString.split(';').reduce<Record<string, string>>((acc, entry) => {
    const [key, value] = entry.split(':').map((part) => part.trim());
    if (!key || !value) return acc;
    const camelKey = key.replace(/-([a-z])/g, (_, char: string) => char.toUpperCase());
    acc[camelKey] = value;
    return acc;
  }, {});
}

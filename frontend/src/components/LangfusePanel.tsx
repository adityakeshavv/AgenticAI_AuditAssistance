import type { AuditResponse } from '../types/audit';

interface Props {
  response: AuditResponse;
}

export function LangfusePanel({ response }: Props) {
  const langfuse = response.traceability?.langfuse;
  const embedUrl = import.meta.env.VITE_LANGFUSE_URL as string | undefined;
  const traceId = langfuse?.trace_id || 'n/a';
  const dashboardUrl = langfuse?.trace_url || embedUrl || '';

  return (
    <div className="stack">
      <div className="grid-3" style={{ gap: '1rem' }}>
        <div className="card-sm">
          <p className="label">Langfuse Trace</p>
          <p className="body-copy" style={{ wordBreak: 'break-all' }}>{traceId}</p>
        </div>
        <div className="card-sm">
          <p className="label">Trace Enabled</p>
          <p className="body-copy">{langfuse?.enabled ? 'Yes' : 'No'}</p>
        </div>
        <div className="card-sm">
          <p className="label">Session</p>
          <p className="body-copy">{langfuse?.session_id || 'n/a'}</p>
        </div>
      </div>

      {dashboardUrl ? (
        <div className="card-sm" style={{ padding: 0, overflow: 'hidden', minHeight: '65vh' }}>
          <div className="flex-between" style={{ padding: '0.9rem 1rem', borderBottom: '1px solid var(--border)' }}>
            <div>
              <p className="label" style={{ marginBottom: 0 }}>Langfuse Workspace</p>
              <p className="small-copy" style={{ color: 'var(--text-muted)' }}>Open the observability dashboard inside the app.</p>
            </div>
            <a className="source-pill" href={dashboardUrl} target="_blank" rel="noreferrer">
              Open in new tab
            </a>
          </div>
          <iframe
            title="Langfuse dashboard"
            src={dashboardUrl}
            style={{ width: '100%', height: 'calc(65vh - 64px)', border: '0', background: 'var(--panel-alt)' }}
          />
        </div>
      ) : (
        <div className="card-sm">
          <p className="label">Langfuse Workspace</p>
          <p className="body-copy">
            Add <code>VITE_LANGFUSE_URL</code> in the frontend environment or configure a Langfuse host in the backend to display the dashboard here.
          </p>
        </div>
      )}
    </div>
  );
}

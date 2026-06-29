import type { AuditResponse, ExecutionMetadataRecord } from '../types/audit';
import { AgentWorkflow } from './workflow/AgentWorkflow';

interface Props { response: AuditResponse; }

function prettyAgent(a: string) {
  return a.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()).trim();
}
function statusBadge(v?: string | null) {
  const n = (v || '').toLowerCase();
  if (n.includes('fail')) return 'badge-failed';
  if (n.includes('skip')) return 'badge-skipped';
  if (n.includes('run') || n.includes('act')) return 'badge-running';
  return 'badge-completed';
}
function statusLabel(v?: string | null) {
  const n = (v || '').toLowerCase();
  if (n.includes('fail')) return 'Failed';
  if (n.includes('skip')) return 'Skipped';
  if (n.includes('run') || n.includes('act')) return 'Running';
  return 'Completed';
}

function buildExecution(meta: ExecutionMetadataRecord[], fallback: string[]) {
  const entries = meta.length > 0
    ? meta
    : fallback.map((a) => ({ agent: a, status: 'completed', reason_selected: 'Planner-selected execution step.' }));
  return entries.map((e) => ({
    name: prettyAgent(String(e.agent || 'Unknown')),
    status: statusLabel(e.status),
    badgeClass: statusBadge(e.status),
    reason: String(e.reason_selected || 'Planner-selected execution step.'),
  }));
}

export function TraceabilityPanel({ response }: Props) {
  const execMeta = response.execution_metadata || response.traceability.execution_metadata || [];
  const execution = buildExecution(execMeta, response.agents_used);
  const reasoningSteps = response.traceability.reasoning_path;
  const sourcesPills = (response.traceability.sources_used || []).filter(Boolean);

  return (
    <div className="stack">
      {/* Execution Summary */}
      <div className="card-sm">
        <p className="label" style={{ marginBottom: '0.75rem' }}>Execution Summary — Agent Order & Status</p>
        {execution.length > 0 ? (
          <div className="stack-sm">
            {execution.map((e, i) => (
              <div
                key={`${e.name}-${i}`}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: '0.75rem',
                  background: 'var(--bg-panel)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)', padding: '0.75rem 1rem',
                }}
              >
                <span style={{
                  width: 26, height: 26, borderRadius: '50%',
                  background: 'rgba(59,130,246,0.12)', color: 'var(--accent-blue)',
                  display: 'grid', placeItems: 'center', fontSize: '0.75rem',
                  fontWeight: 700, flexShrink: 0,
                }}>{i + 1}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <strong style={{ fontSize: '0.88rem' }}>{e.name}</strong>
                    <span className={`badge ${e.badgeClass}`}>{e.status}</span>
                  </div>
                  <p className="small-copy">{e.reason}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="body-copy">No execution metadata was returned.</p>
        )}
      </div>

      {/* Sources */}
      {sourcesPills.length > 0 && (
        <div className="card-sm">
          <p className="label" style={{ marginBottom: '0.5rem' }}>Data Sources Used</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {sourcesPills.map((s) => (
              <span key={s} className="source-pill">{String(s)}</span>
            ))}
          </div>
        </div>
      )}

      {/* Reasoning Path */}
      {reasoningSteps.length > 0 && (
        <div className="card-sm">
          <p className="label" style={{ marginBottom: '0.75rem' }}>Reasoning Path ({reasoningSteps.length} steps)</p>
          <div className="timeline">
            {reasoningSteps.map((step, i) => (
              <div key={i} className="timeline-item">
                <div className="timeline-dot">{i + 1}</div>
                <div className="timeline-body">{step}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interactive Workflow */}
      <AgentWorkflow response={response} />

      {/* Developer Details */}
      <details style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '1rem' }}>
        <summary style={{ cursor: 'pointer', listStyle: 'none', color: 'var(--text-secondary)', fontSize: '0.87rem', fontWeight: 600 }}>
          ▶ Developer Details — Raw Response Metadata
        </summary>
        <div className="stack-sm" style={{ marginTop: '1rem' }}>
          <div>
            <p className="label">Intent</p>
            <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {JSON.stringify(response.intent, null, 2)}
            </pre>
          </div>
          <div>
            <p className="label">Traceability</p>
            <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {JSON.stringify(response.traceability, null, 2)}
            </pre>
          </div>
        </div>
      </details>
    </div>
  );
}

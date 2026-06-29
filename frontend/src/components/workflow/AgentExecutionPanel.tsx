import type { AuditResponse } from '../../types/audit';
import type { WorkflowStatus } from './WorkflowNode';

export interface WorkflowNodeModel {
  id: string;
  label: string;
  status: WorkflowStatus;
  description: string;
  purpose: string;
  input: string;
  output: string;
  summary: string;
  evidenceCount?: number;
  sourceCount?: number;
}

interface Props { node: WorkflowNodeModel | null; response: AuditResponse; active?: boolean; }

function badgeClass(active: boolean, status: string) {
  if (active) return 'badge-running';
  switch (status.toLowerCase()) {
    case 'completed': return 'badge-completed';
    case 'skipped':   return 'badge-skipped';
    case 'failed':    return 'badge-failed';
    default:          return 'badge-running';
  }
}

export function AgentExecutionPanel({ node, response, active = false }: Props) {
  if (!node) {
    return (
      <article className="dashboard-widget" style={{ alignContent: 'start' }}>
        <div className="dashboard-widget-header">
          <div>
            <p className="label" style={{ margin: 0 }}>Agent Execution</p>
            <h3 style={{ margin: '0.25rem 0 0' }}>Select a workflow step</h3>
          </div>
        </div>
        <p className="body-copy">Click any step to inspect its purpose, inputs, outputs, and processing details.</p>
      </article>
    );
  }

  const evCount = node.evidenceCount ?? (response.structured_evidence.length + response.document_evidence.length);
  const srcCount = node.sourceCount ?? response.sources.length;

  return (
    <article className="dashboard-widget" style={{ alignContent: 'start' }}>
      <div className="dashboard-widget-header">
        <div>
          <p className="label" style={{ margin: 0 }}>Agent Execution</p>
          <h3 style={{ margin: '0.25rem 0 0' }}>{node.label}</h3>
        </div>
        <span className={`badge ${badgeClass(active, node.status)}`}>
          {active ? 'Active' : node.status}
        </span>
      </div>

      <div className="stack-sm">
        <div>
          <p className="label" style={{ marginBottom: '0.25rem' }}>Purpose</p>
          <p className="body-copy">{node.purpose}</p>
        </div>
        <div className="divider" />
        <div>
          <p className="label" style={{ marginBottom: '0.25rem' }}>Input Received</p>
          <p className="body-copy" style={{ fontSize: '0.82rem', fontFamily: 'monospace', background: 'var(--bg-input)', padding: '0.5rem 0.75rem', borderRadius: '6px', wordBreak: 'break-word' }}>
            {node.input}
          </p>
        </div>
        <div>
          <p className="label" style={{ marginBottom: '0.25rem' }}>Output Generated</p>
          <p className="body-copy" style={{ fontSize: '0.82rem', fontFamily: 'monospace', background: 'var(--bg-input)', padding: '0.5rem 0.75rem', borderRadius: '6px', wordBreak: 'break-word' }}>
            {node.output}
          </p>
        </div>
        <div className="divider" />
        <div>
          <p className="label" style={{ marginBottom: '0.25rem' }}>Processing Summary</p>
          <p className="body-copy">{node.summary}</p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginTop: '0.25rem' }}>
          <div style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '0.6rem 0.85rem' }}>
            <p className="label" style={{ margin: '0 0 0.2rem' }}>Evidence Items</p>
            <strong style={{ fontSize: '1.2rem', color: 'var(--accent-blue)' }}>{evCount}</strong>
          </div>
          <div style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '0.6rem 0.85rem' }}>
            <p className="label" style={{ margin: '0 0 0.2rem' }}>Sources Touched</p>
            <strong style={{ fontSize: '1.2rem', color: 'var(--accent-cyan)' }}>{srcCount}</strong>
          </div>
        </div>
      </div>
    </article>
  );
}

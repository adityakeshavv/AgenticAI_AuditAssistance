import type { InvestigationState } from '../../types/audit';

interface Props {
  state: InvestigationState;
  turnCount: number;
}

function StatRow({ label, value, color = 'var(--accent-blue)' }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '0.5rem 0.75rem',
      background: 'var(--bg-panel)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-sm)',
      fontSize: '0.83rem',
    }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <strong style={{ color }}>{value}</strong>
    </div>
  );
}

export function InvestigationSidebar({ state, turnCount }: Props) {
  const riskColor = state.risk_rating === 'HIGH' || state.risk_rating === 'CRITICAL'
    ? 'var(--accent-red)' : state.risk_rating === 'MEDIUM'
    ? 'var(--accent-amber)' : 'var(--accent-green)';

  return (
    <aside style={{
      width: 260, flexShrink: 0,
      display: 'flex', flexDirection: 'column', gap: '1rem',
      padding: '1rem', borderLeft: '1px solid var(--border)', overflowY: 'auto',
    }}>
      <div>
        <p className="label" style={{ marginBottom: '0.5rem' }}>Active Investigation</p>
        <div className="stack-sm">
          <StatRow label="Status" value={state.status === 'in_progress' ? 'In Progress' : state.status === 'idle' ? 'Idle' : state.status} color="var(--accent-cyan)" />
          <StatRow label="Turns" value={turnCount} />
          {state.entity_type && <StatRow label="Focus" value={state.entity_type} />}
          {state.risk_rating && <StatRow label="Risk" value={state.risk_rating} color={riskColor} />}
          <StatRow label="Transactions" value={state.transaction_count} />
          <StatRow label="Documents" value={state.document_count} />
          <StatRow label="Findings" value={state.finding_count} />
        </div>
      </div>

      {state.entity_ids.length > 0 && (
        <div>
          <p className="label" style={{ marginBottom: '0.5rem' }}>Entities Reviewed</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
            {state.entity_ids.slice(0, 8).map((id) => (
              <span key={id} className="source-pill" style={{ fontSize: '0.72rem' }}>{id}</span>
            ))}
            {state.entity_ids.length > 8 && <span className="small-copy">+{state.entity_ids.length - 8} more</span>}
          </div>
        </div>
      )}

      {state.topics.length > 0 && (
        <div>
          <p className="label" style={{ marginBottom: '0.5rem' }}>Topics</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
            {state.topics.map((t) => (
              <span key={t} style={{ padding: '0.2rem 0.55rem', background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.2)', borderRadius: '999px', fontSize: '0.75rem', color: '#c4b5fd' }}>{t}</span>
            ))}
          </div>
        </div>
      )}

      {state.key_findings.length > 0 && (
        <div>
          <p className="label" style={{ marginBottom: '0.5rem' }}>Key Findings ({state.key_findings.length})</p>
          <div className="stack-sm">
            {state.key_findings.slice(0, 4).map((f, i) => (
              <div key={i} style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5, padding: '0.4rem 0.6rem', background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', borderLeft: '2px solid var(--accent-blue)' }}>{f}</div>
            ))}
            {state.key_findings.length > 4 && <p className="small-copy">+{state.key_findings.length - 4} more</p>}
          </div>
        </div>
      )}

      {state.recommendations.length > 0 && (
        <div>
          <p className="label" style={{ marginBottom: '0.5rem' }}>Recommendations</p>
          <div className="stack-sm">
            {state.recommendations.slice(0, 3).map((r, i) => (
              <div key={i} style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5, padding: '0.4rem 0.6rem', background: 'rgba(16,185,129,0.05)', border: '1px solid rgba(16,185,129,0.15)', borderRadius: 'var(--radius-sm)' }}>{r}</div>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}

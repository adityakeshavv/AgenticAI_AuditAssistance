export type WorkflowStatus = 'Completed' | 'Active' | 'Waiting' | 'Skipped' | 'Failed';

interface Props {
  label: string;
  description: string;
  status: WorkflowStatus;
  active?: boolean;
  selected?: boolean;
  onSelect: () => void;
}

function statusStyle(s: WorkflowStatus) {
  switch (s) {
    case 'Completed': return { bg: 'rgba(16,185,129,0.1)', color: '#34d399', border: 'rgba(16,185,129,0.3)' };
    case 'Active':    return { bg: 'rgba(59,130,246,0.1)', color: '#93c5fd', border: 'rgba(59,130,246,0.3)' };
    case 'Skipped':   return { bg: 'rgba(100,116,139,0.1)', color: '#94a3b8', border: 'rgba(100,116,139,0.2)' };
    case 'Failed':    return { bg: 'rgba(239,68,68,0.1)', color: '#f87171', border: 'rgba(239,68,68,0.3)' };
    default:          return { bg: 'rgba(245,158,11,0.1)', color: '#fbbf24', border: 'rgba(245,158,11,0.3)' };
  }
}

export function WorkflowNode({ label, description, status, active = false, selected, onSelect }: Props) {
  const displayStatus = active ? 'Active' : status;
  const s = statusStyle(displayStatus);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`workflow-node${selected ? ' selected' : ''}`}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <strong style={{ display: 'block', fontSize: '0.88rem', color: 'var(--text-primary)', marginBottom: '0.2rem' }}>
          {label}
        </strong>
        <p className="small-copy" style={{ margin: 0, lineHeight: 1.4 }}>{description}</p>
      </div>
      <span style={{
        padding: '0.25rem 0.6rem', borderRadius: '999px', fontSize: '0.75rem',
        fontWeight: 700, whiteSpace: 'nowrap', flexShrink: 0,
        background: s.bg, color: s.color, border: `1px solid ${s.border}`,
      }}>
        {displayStatus}
      </span>
    </button>
  );
}

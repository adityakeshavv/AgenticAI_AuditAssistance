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
    case 'Completed': return { bg: 'rgba(24,167,125,0.1)', color: '#0f8a66', border: 'rgba(24,167,125,0.28)' };
    case 'Active':    return { bg: 'rgba(95,111,232,0.1)', color: '#5f6fe8', border: 'rgba(95,111,232,0.28)' };
    case 'Skipped':   return { bg: 'rgba(100,116,139,0.1)', color: '#64748b', border: 'rgba(100,116,139,0.2)' };
    case 'Failed':    return { bg: 'rgba(217,79,112,0.1)', color: '#c0264d', border: 'rgba(217,79,112,0.28)' };
    default:          return { bg: 'rgba(217,119,6,0.1)', color: '#b45309', border: 'rgba(217,119,6,0.28)' };
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

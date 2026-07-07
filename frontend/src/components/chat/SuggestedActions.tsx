import type { SuggestedAction } from '../../types/audit';

interface Props {
  actions: SuggestedAction[];
  onSelect: (action: SuggestedAction) => void;
  disabled?: boolean;
}

export function SuggestedActions({ actions, onSelect, disabled }: Props) {
  if (!actions.length) return null;
  return (
    <div style={{ padding: '0.5rem 0', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
      <p style={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)', margin: '0 0 0.25rem' }}>Suggested Next Steps</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
        {actions.map((a) => (
          <button
            key={a.id}
            onClick={() => onSelect(a)}
            disabled={disabled}
            title={a.description}
            style={{
              padding: '0.4rem 0.85rem',
              background: 'rgba(95,111,232,0.08)',
              border: '1px solid rgba(95,111,232,0.18)',
              borderRadius: '999px',
              fontSize: '0.82rem',
              color: '#5f6fe8',
              cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.5 : 1,
              transition: 'all 0.15s',
              whiteSpace: 'nowrap',
            }}
            onMouseEnter={(e) => { if (!disabled) (e.currentTarget.style.background = 'rgba(95,111,232,0.14)'); }}
            onMouseLeave={(e) => { (e.currentTarget.style.background = 'rgba(95,111,232,0.08)'); }}
          >
            {a.label}
          </button>
        ))}
      </div>
    </div>
  );
}

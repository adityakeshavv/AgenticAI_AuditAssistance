export function WorkflowEdge({ count }: { count: number }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '16px', color: 'var(--text-muted)', fontSize: '0.7rem', gap: '0.35rem',
    }}>
      <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
      <span style={{ opacity: 0.5 }}>step {count}</span>
      <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
    </div>
  );
}

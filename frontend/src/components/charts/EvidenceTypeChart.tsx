const fallbackData = [
  { label: 'PDF', value: 18, color: '#3b82f6' },
  { label: 'Email', value: 24, color: '#8b5cf6' },
  { label: 'Policy', value: 14, color: '#10b981' },
  { label: 'Metadata', value: 31, color: '#f59e0b' },
  { label: 'Structured', value: 39, color: '#ef4444' },
];

export function EvidenceTypeChart({ data = fallbackData }: { data?: typeof fallbackData }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <article className="dashboard-widget">
      <div className="dashboard-widget-header">
        <div>
          <p className="label" style={{ margin: 0 }}>Evidence Types</p>
          <h3 style={{ margin: '0.25rem 0 0' }}>Sources used in investigations</h3>
        </div>
      </div>
      <div className="bar-chart">
        {data.map((item) => (
          <div key={item.label} className="bar-row">
            <div className="bar-label">
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: item.color, display: 'inline-block' }} />
                {item.label}
              </span>
              <strong style={{ color: item.color }}>{item.value}</strong>
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${(item.value / max) * 100}%`, background: item.color }} />
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}

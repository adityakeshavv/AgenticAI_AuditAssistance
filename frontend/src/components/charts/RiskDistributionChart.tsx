const fallbackData = [
  { label: 'High Risk', value: 28, color: '#ef4444' },
  { label: 'Medium Risk', value: 46, color: '#f59e0b' },
  { label: 'Low Risk', value: 26, color: '#10b981' },
];

export function RiskDistributionChart({ data = fallbackData }: { data?: typeof fallbackData }) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const radius = 42;
  const stroke = 14;
  const circ = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <article className="dashboard-widget">
      <div className="dashboard-widget-header">
        <div>
          <p className="label" style={{ margin: 0 }}>Risk Distribution</p>
          <h3 style={{ margin: '0.25rem 0 0' }}>Open risk profile</h3>
        </div>
      </div>
      <div className="donut-chart">
        <svg viewBox="0 0 120 120" width="120" height="120" aria-label="Risk distribution donut chart" role="img" style={{ flexShrink: 0 }}>
          <circle cx="60" cy="60" r={radius} fill="none" stroke="rgba(148,163,184,0.1)" strokeWidth={stroke} />
          {data.map((item) => {
            const dash = (item.value / total) * circ;
            const seg = (
              <circle
                key={item.label}
                cx="60" cy="60" r={radius}
                fill="none" stroke={item.color}
                strokeWidth={stroke}
                strokeDasharray={`${dash} ${circ - dash}`}
                strokeDashoffset={-offset}
                strokeLinecap="butt"
                transform="rotate(-90 60 60)"
                style={{ transition: 'stroke-dasharray 0.6s ease' }}
              />
            );
            offset += dash;
            return seg;
          })}
          <text x="60" y="57" textAnchor="middle" fill="#e8f0fe" fontSize="18" fontWeight="800">{total}</text>
          <text x="60" y="73" textAnchor="middle" fill="#8fa8cc" fontSize="10">cases</text>
        </svg>
        <div className="donut-legend">
          {data.map((item) => (
            <div key={item.label} className="legend-item">
              <span className="legend-dot" style={{ background: item.color }} />
              <span style={{ flex: 1, fontSize: '0.83rem', color: 'var(--text-secondary)' }}>{item.label}</span>
              <strong style={{ color: item.color, fontWeight: 700 }}>{item.value}</strong>
              <span className="small-copy" style={{ marginLeft: '0.35rem' }}>({((item.value / total) * 100).toFixed(0)}%)</span>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}

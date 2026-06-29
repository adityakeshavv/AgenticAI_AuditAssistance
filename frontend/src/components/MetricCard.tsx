import type { ReactNode } from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  detail?: string;
  accent?: string;
  icon?: ReactNode;
  trend?: string;
  trendDirection?: 'up' | 'down' | 'flat';
}

export function MetricCard({ label, value, detail, accent = '#3b82f6', icon, trend, trendDirection = 'flat' }: MetricCardProps) {
  const trendColor = trendDirection === 'up' ? 'var(--accent-green)' : trendDirection === 'down' ? 'var(--accent-red)' : 'var(--text-muted)';

  return (
    <article className="kpi-card" style={{ '--kpi-accent': accent } as React.CSSProperties}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.75rem' }}>
        <div>
          <p className="label" style={{ marginBottom: '0.4rem' }}>{label}</p>
          <div className="kpi-value">{value}</div>
        </div>
        {icon && (
          <div
            aria-hidden="true"
            style={{
              width: '2.5rem', height: '2.5rem', borderRadius: '10px',
              display: 'grid', placeItems: 'center',
              background: `${accent}1a`, color: accent, flexShrink: 0,
              fontSize: '1.1rem', fontWeight: 700,
            }}
          >
            {icon}
          </div>
        )}
      </div>
      {trend && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: trendColor, fontSize: '0.82rem', fontWeight: 600 }}>
          <span>{trendDirection === 'up' ? '↗' : trendDirection === 'down' ? '↘' : '•'}</span>
          <span>{trend}</span>
        </div>
      )}
      {detail && <p className="small-copy" style={{ lineHeight: 1.5 }}>{detail}</p>}
    </article>
  );
}

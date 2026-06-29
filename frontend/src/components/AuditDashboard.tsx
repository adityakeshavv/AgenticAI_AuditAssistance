import { useState } from 'react';
import { MetricCard } from './MetricCard';
import { RecentInvestigations } from './RecentInvestigations';
import { SystemOverview } from './SystemOverview';
import { AgentActivityChart } from './charts/AgentActivityChart';
import { EvidenceTypeChart } from './charts/EvidenceTypeChart';
import { RiskDistributionChart } from './charts/RiskDistributionChart';

interface AuditDashboardProps {
  onNavigateToWorkspace: () => void;
}

const SAMPLE_QUERIES = [
  'Investigate vendor VND-02731 for compliance issues',
  'Show all flagged transactions above $50,000',
  'Investigate transaction TXN-C8972378',
  'Which vendors have high-risk payment patterns?',
];

const workflow = [
  { id: 'intent', label: 'Intent Extraction', desc: 'Parses the audit query into structured intent.' },
  { id: 'planner', label: 'Investigation Planner', desc: 'Routes the query to the correct audit agents.' },
  { id: 'transaction', label: 'Transaction Agent', desc: 'Retrieves matching transaction records.' },
  { id: 'document', label: 'Document Retrieval Agent', desc: 'Links supporting evidence documents.' },
  { id: 'aggregator', label: 'Evidence Aggregator', desc: 'Merges structured and document evidence.' },
  { id: 'composer', label: 'Response Composer', desc: 'Produces the final audit finding.' },
];

export function AuditDashboard({ onNavigateToWorkspace }: AuditDashboardProps) {
  const [activeWorkflow, setActiveWorkflow] = useState('intent');

  const kpis = [
    {
      label: 'Total Transactions',
      value: '128,450',
      detail: 'All processed transaction records available for audit review.',
      accent: '#3b82f6',
      trend: '+4.6% this week',
      trendDirection: 'up' as const,
      icon: '◎',
    },
    {
      label: 'Flagged Transactions',
      value: '4,218',
      detail: 'Transactions marked for enhanced review and follow-up.',
      accent: '#f59e0b',
      trend: '+128 since yesterday',
      trendDirection: 'up' as const,
      icon: '!',
    },
    {
      label: 'High Risk Findings',
      value: '327',
      detail: 'Cases elevated by risk scoring and document signals.',
      accent: '#ef4444',
      trend: '+12 open cases',
      trendDirection: 'up' as const,
      icon: '▲',
    },
    {
      label: 'Supporting Documents',
      value: '835',
      detail: 'Metadata-linked enterprise documents ready for retrieval.',
      accent: '#10b981',
      trend: '+31 linked documents',
      trendDirection: 'up' as const,
      icon: '▣',
    },
    {
      label: 'Active Investigations',
      value: '61',
      detail: 'Active and archived investigations available for review.',
      accent: '#8b5cf6',
      trend: 'Stable this week',
      trendDirection: 'flat' as const,
      icon: '⌕',
    },
  ];

  const riskDistribution = [
    { label: 'High Risk', value: 28, color: '#ef4444' },
    { label: 'Medium Risk', value: 46, color: '#f59e0b' },
    { label: 'Low Risk', value: 26, color: '#10b981' },
  ];

  const evidenceDistribution = [
    { label: 'PDF', value: 18, color: '#3b82f6' },
    { label: 'Email', value: 24, color: '#8b5cf6' },
    { label: 'Policy', value: 14, color: '#10b981' },
    { label: 'Metadata', value: 31, color: '#f59e0b' },
    { label: 'Structured', value: 39, color: '#ef4444' },
  ];

  const agentActivity = [
    { label: 'Transaction Agent', value: 42, color: '#3b82f6' },
    { label: 'Vendor Agent', value: 27, color: '#10b981' },
    { label: 'Compliance Agent', value: 19, color: '#f59e0b' },
    { label: 'Document Retrieval', value: 31, color: '#8b5cf6' },
  ];

  const selectedStep = workflow.find((w) => w.id === activeWorkflow) || workflow[0];

  return (
    <div style={{ display: 'grid', gap: '1.5rem' }}>
      {/* Hero */}
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow" style={{ marginBottom: '0.5rem' }}>Audit Operations Center</p>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '0.5rem' }}>
            Executive Audit Dashboard
          </h1>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '55ch', lineHeight: 1.6 }}>
            Monitor audit coverage, review exceptions, and launch the investigative workspace when you need to drill into a case.
          </p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', flexShrink: 0 }}>
          <button className="btn btn-primary" onClick={onNavigateToWorkspace} style={{ padding: '0.75rem 1.5rem', fontSize: '0.95rem' }}>
            Launch Audit Copilot →
          </button>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textAlign: 'center' }}>Chat, investigate, and follow up conversationally</span>
        </div>
      </div>

      {/* KPI Grid */}
      <div>
        <p className="label" style={{ marginBottom: '0.75rem' }}>Key Performance Indicators</p>
        <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
          {kpis.map((kpi) => (
            <MetricCard key={kpi.label} {...kpi} />
          ))}
        </div>
      </div>

      {/* Charts Row */}
      <div>
        <p className="label" style={{ marginBottom: '0.75rem' }}>Analytics Overview</p>
        <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
          <RiskDistributionChart data={riskDistribution} />
          <EvidenceTypeChart data={evidenceDistribution} />
          <AgentActivityChart data={agentActivity} />
        </div>
      </div>

      {/* Middle row: System Overview + Recent Investigations */}
      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))' }}>
        <SystemOverview />
        <RecentInvestigations onOpenInvestigation={onNavigateToWorkspace} />
      </div>

      {/* Quick Queries + Agent Workflow */}
      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: '1fr 1.5fr' }}>
        {/* Quick Queries */}
        <div className="card">
          <p className="label">Quick Queries</p>
          <p className="body-copy" style={{ marginBottom: '0.9rem' }}>Click any query to open it in the audit workspace.</p>
          <div className="stack-sm">
            {SAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                className="investigation-item"
                onClick={onNavigateToWorkspace}
                style={{ fontSize: '0.85rem' }}
              >
                <span style={{ color: 'var(--accent-blue)', fontSize: '1rem', flexShrink: 0 }}>→</span>
                <span>{q}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Agent Workflow Preview */}
        <div className="card">
          <p className="label">Agent Workflow Pipeline</p>
          <p className="body-copy" style={{ marginBottom: '0.9rem' }}>Interactive overview of the multi-agent audit system.</p>
          <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: '1fr 1fr' }}>
            <div className="stack-sm">
              {workflow.map((step, i) => (
                <div key={step.id}>
                  <button
                    onClick={() => setActiveWorkflow(step.id)}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      background: activeWorkflow === step.id ? 'rgba(59,130,246,0.1)' : 'var(--bg-panel)',
                      border: `1px solid ${activeWorkflow === step.id ? 'rgba(59,130,246,0.4)' : 'var(--border)'}`,
                      borderRadius: 'var(--radius-sm)',
                      padding: '0.5rem 0.75rem',
                      color: 'var(--text-primary)',
                      fontSize: '0.83rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                    }}
                  >
                    <span
                      style={{
                        width: 20, height: 20, borderRadius: '50%',
                        background: activeWorkflow === step.id ? 'var(--accent-blue)' : 'var(--bg-card)',
                        color: activeWorkflow === step.id ? '#fff' : 'var(--text-muted)',
                        display: 'grid', placeItems: 'center', fontSize: '0.7rem', fontWeight: 700, flexShrink: 0
                      }}
                    >
                      {i + 1}
                    </span>
                    {step.label}
                  </button>
                  {i < workflow.length - 1 && (
                    <div style={{ width: 1, height: 8, background: 'var(--border)', margin: '0 0 0 19px' }} />
                  )}
                </div>
              ))}
            </div>
            <div style={{ padding: '0.75rem', background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', display: 'grid', alignContent: 'start', gap: '0.5rem' }}>
              <p className="label" style={{ margin: 0 }}>Active Step</p>
              <strong style={{ fontSize: '0.9rem', color: 'var(--text-accent)' }}>{selectedStep.label}</strong>
              <p className="body-copy" style={{ fontSize: '0.8rem' }}>{selectedStep.desc}</p>
              <div style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border)' }}>
                <span className="badge badge-completed">Operational</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

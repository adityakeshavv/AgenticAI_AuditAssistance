import { useState } from 'react';
import { MetricCard } from './MetricCard';
import { RecentInvestigations } from './RecentInvestigations';
import { SystemOverview } from './SystemOverview';
import { AgentActivityChart } from './charts/AgentActivityChart';
import { EvidenceTypeChart } from './charts/EvidenceTypeChart';
import { RiskDistributionChart } from './charts/RiskDistributionChart';

interface AuditDashboardProps {
  onNavigateToWorkspace: () => void;
  onNavigateToSources: () => void;
  onNavigateToAudit: () => void;
  onNavigateToChat: () => void;
  onNavigateToGraph: () => void;
  activeWorkspaceName: string | null;
  hasSelectedSource: boolean;
  workspaceCount: number;
}

const SAMPLE_QUERIES = [
  'Investigate vendor VND-02731 for compliance issues',
  'Show all flagged transactions above $50,000',
  'Show vendors with expired compliance certifications',
  'Which approvals exceeded authority limits?',
];

const workflow = [
  { id: 'intent', label: 'Intent Extraction', desc: 'Parses the audit query into structured intent.' },
  { id: 'planner', label: 'Investigation Planner', desc: 'Routes the query to the correct audit agents.' },
  { id: 'transaction', label: 'Transaction Agent', desc: 'Retrieves matching transaction records.' },
  { id: 'document', label: 'Document Retrieval Agent', desc: 'Links supporting evidence documents.' },
  { id: 'aggregator', label: 'Evidence Aggregator', desc: 'Merges structured and document evidence.' },
  { id: 'composer', label: 'Response Composer', desc: 'Produces the final audit finding.' },
];

export function AuditDashboard({
  onNavigateToWorkspace,
  onNavigateToSources,
  onNavigateToAudit,
  onNavigateToChat,
  onNavigateToGraph,
  activeWorkspaceName,
  hasSelectedSource,
  workspaceCount,
}: AuditDashboardProps) {
  const [activeWorkflow, setActiveWorkflow] = useState('intent');

  const primaryActionLabel = !activeWorkspaceName
    ? 'Open Workspaces'
    : !hasSelectedSource
      ? 'Open Data Sources'
      : 'Open Audit Workspace';

  const handlePrimaryAction = !activeWorkspaceName
    ? onNavigateToWorkspace
    : !hasSelectedSource
      ? onNavigateToSources
      : onNavigateToAudit;

  const kpis = [
    {
      label: 'Total Transactions',
      value: '128,450',
      detail: 'All processed transaction records available for audit review.',
      accent: '#3b82f6',
      trend: '+4.6% this week',
      trendDirection: 'up' as const,
      icon: 'TX',
    },
    {
      label: 'Flagged Transactions',
      value: '4,218',
      detail: 'Transactions marked for enhanced review and follow-up.',
      accent: '#f59e0b',
      trend: '+128 since yesterday',
      trendDirection: 'up' as const,
      icon: 'FR',
    },
    {
      label: 'High Risk Findings',
      value: '327',
      detail: 'Cases elevated by risk scoring and document signals.',
      accent: '#ef4444',
      trend: '+12 open cases',
      trendDirection: 'up' as const,
      icon: 'HR',
    },
    {
      label: 'Supporting Documents',
      value: '835',
      detail: 'Metadata-linked enterprise documents ready for retrieval.',
      accent: '#10b981',
      trend: '+31 linked documents',
      trendDirection: 'up' as const,
      icon: 'DOC',
    },
    {
      label: 'Active Investigations',
      value: '61',
      detail: 'Active and archived investigations available for review.',
      accent: '#8b5cf6',
      trend: 'Stable this week',
      trendDirection: 'flat' as const,
      icon: 'INV',
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

  const setupSteps = [
    {
      title: 'Create or select a workspace',
      status: activeWorkspaceName ? 'Ready' : 'Start here',
      detail: activeWorkspaceName
        ? `Active workspace: ${activeWorkspaceName}`
        : 'Pick the workspace that will scope the audit session.',
      actionLabel: activeWorkspaceName ? 'Change Workspace' : 'Open Workspaces',
      action: onNavigateToWorkspace,
    },
    {
      title: 'Connect a data source',
      status: hasSelectedSource ? 'Ready' : 'Pending',
      detail: hasSelectedSource
        ? 'A source is already linked to the active workspace.'
        : 'Add a database or document source before starting the review.',
      actionLabel: 'Open Data Sources',
      action: onNavigateToSources,
    },
    {
      title: 'Open the audit workspace',
      status: 'Ready',
      detail: 'Use the audit workspace to ask a question and inspect evidence-backed findings.',
      actionLabel: 'Open Audit Workspace',
      action: onNavigateToAudit,
    },
    {
      title: 'Explore the knowledge graph',
      status: hasSelectedSource ? 'Ready' : 'Pending',
      detail: 'Inspect entity relationships across vendors, transactions, documents, and findings.',
      actionLabel: 'Open Graph',
      action: onNavigateToGraph,
    },
    {
      title: 'Continue in Copilot Chat',
      status: 'Ready',
      detail: 'Ask follow-up questions after the first response is generated.',
      actionLabel: 'Open Chat',
      action: onNavigateToChat,
    },
  ];

  return (
    <div style={{ display: 'grid', gap: '1.5rem' }}>
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
          <button className="btn btn-primary" onClick={handlePrimaryAction} style={{ padding: '0.75rem 1.5rem', fontSize: '0.95rem' }}>
            {primaryActionLabel}
          </button>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textAlign: 'center' }}>
            Follow the setup journey before opening the assistant
          </span>
        </div>
      </div>

      <div>
        <p className="label" style={{ marginBottom: '0.75rem' }}>Start Here</p>
        <div className="grid-2" style={{ gap: '1rem' }}>
          {setupSteps.map((step) => (
            <div key={step.title} className="card">
              <div className="flex-between" style={{ gap: '0.75rem', alignItems: 'flex-start' }}>
                <div style={{ minWidth: 0 }}>
                  <p className="label" style={{ marginBottom: '0.35rem' }}>{step.title}</p>
                  <strong style={{ display: 'block', marginBottom: '0.35rem' }}>{step.status}</strong>
                  <p className="body-copy" style={{ lineHeight: 1.6 }}>{step.detail}</p>
                </div>
                <button className="btn btn-secondary" type="button" onClick={step.action} style={{ flexShrink: 0 }}>
                  {step.actionLabel}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <p className="label" style={{ marginBottom: '0.75rem' }}>Key Performance Indicators</p>
        <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
          {kpis.map((kpi) => (
            <MetricCard key={kpi.label} {...kpi} />
          ))}
        </div>
      </div>

      <div>
        <p className="label" style={{ marginBottom: '0.75rem' }}>Analytics Overview</p>
        <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
          <RiskDistributionChart data={riskDistribution} />
          <EvidenceTypeChart data={evidenceDistribution} />
          <AgentActivityChart data={agentActivity} />
        </div>
      </div>

      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))' }}>
        <SystemOverview />
        <RecentInvestigations onOpenInvestigation={onNavigateToAudit} />
      </div>

      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: '1fr 1.5fr' }}>
        <div className="card">
          <p className="label">Quick Queries</p>
          <p className="body-copy" style={{ marginBottom: '0.9rem' }}>Click any query to open it in the audit workspace.</p>
          <div className="stack-sm">
            {SAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                className="investigation-item"
                onClick={onNavigateToAudit}
                style={{ fontSize: '0.85rem' }}
              >
                <span style={{ color: 'var(--accent-blue)', fontSize: '1rem', flexShrink: 0 }}>&gt;</span>
                <span>{q}</span>
              </button>
            ))}
          </div>
        </div>

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
                        width: 20,
                        height: 20,
                        borderRadius: '50%',
                        background: activeWorkflow === step.id ? 'var(--accent-blue)' : 'var(--bg-card)',
                        color: activeWorkflow === step.id ? '#fff' : 'var(--text-muted)',
                        display: 'grid',
                        placeItems: 'center',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        flexShrink: 0,
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
            <div
              style={{
                padding: '0.75rem',
                background: 'var(--bg-panel)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                display: 'grid',
                alignContent: 'start',
                gap: '0.5rem',
              }}
            >
              <p className="label" style={{ margin: 0 }}>Active Step</p>
              <strong style={{ fontSize: '0.9rem', color: 'var(--text-accent)' }}>{selectedStep.label}</strong>
              <p className="body-copy" style={{ fontSize: '0.8rem' }}>{selectedStep.desc}</p>
              <div style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border)' }}>
                <span className="badge badge-completed">Operational</span>
                <span className="source-pill" style={{ marginLeft: '0.5rem' }}>
                  {workspaceCount > 0 ? `${workspaceCount} workspace(s)` : 'No workspace yet'}
                </span>
                <span className="source-pill" style={{ marginLeft: '0.5rem' }}>
                  {hasSelectedSource ? 'Source connected' : 'Source pending'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

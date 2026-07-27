import { type FormEventHandler, useEffect, useState } from 'react';
import { AuditResponsePanel } from './AuditResponsePanel';
import { FeedbackBanner } from './FeedbackBanner';
import { DocumentViewerModal } from './DocumentViewerModal';
import { submitAuditQuery } from '../services/auditApi';
import { getSelectedDatabaseConnectionId } from '../services/databaseConnectionsApi';
import { getSelectedWorkspaceId } from '../services/workspacesApi';
import type { AuditResponse, CitationRecord } from '../types/audit';

const SAMPLE_QUERIES = [
  'Investigate vendor VND-02731',
  'Show flagged transactions over $50K',
  'Investigate transaction TXN-C8972378',
  'Which policy did TXN-C8972378 violate?',
  'High-risk vendor payment patterns this month',
];

const LOADING_STEPS = [
  'Intent Extraction',
  'Investigation Planner',
  'Transaction Agent',
  'Document Retrieval',
  'Evidence Aggregation',
  'Finding Generation',
  'Validation',
];

export function AuditQueryPage() {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState<AuditResponse | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<CitationRecord | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loadingStepIndex, setLoadingStepIndex] = useState(0);

  useEffect(() => {
    if (!isLoading) {
      setLoadingStepIndex(0);
      return;
    }
    const timer = window.setInterval(() => {
      setLoadingStepIndex((current) => Math.min(current + 1, LOADING_STEPS.length - 1));
    }, 480);
    return () => clearInterval(timer);
  }, [isLoading]);

  const citationCount = response?.citations.length ?? 0;
  const riskRating = response?.risk_rating ?? null;
  const activeWorkspaceId = getSelectedWorkspaceId();
  const activeConnectionId = getSelectedDatabaseConnectionId();

  const handleSubmit: FormEventHandler<HTMLFormElement> = async (event) => {
    event.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setLoadingStepIndex(0);
    setErrorMessage(null);
    setSelectedCitation(null);
    setIsModalOpen(false);

    try {
      const result = await submitAuditQuery(query);
      setResponse(result);
    } catch (error) {
      setResponse(null);
      setErrorMessage(error instanceof Error ? error.message : 'Unable to run audit query.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChip = (value: string) => setQuery(value);

  const handleCitationSelect = (citation: CitationRecord) => {
    setSelectedCitation(citation);
    setIsModalOpen(true);
  };

  const setupSteps = [
    {
      label: 'Workspace',
      detail: activeWorkspaceId ? 'Active workspace selected' : 'Select a workspace in the left rail',
    },
    {
      label: 'Source',
      detail: activeConnectionId ? 'Active source selected' : 'Select a source before running queries',
    },
    {
      label: 'Query',
      detail: 'Ask a question in natural audit language',
    },
    {
      label: 'Review',
      detail: 'Inspect findings, evidence, citations, and traceability',
    },
  ];

  return (
    <div style={{ display: 'grid', gap: '1.5rem', alignItems: 'start' }}>
      <div className="dashboard-hero" style={{ marginBottom: 0, alignItems: 'flex-start' }}>
        <div style={{ maxWidth: '56ch' }}>
          <p className="eyebrow" style={{ marginBottom: '0.4rem' }}>Audit Assistant</p>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Investigation Workspace</h1>
          <p className="body-copy" style={{ marginTop: '0.45rem' }}>
            Ask a question, inspect the evidence, and review the resulting audit findings all in one place.
          </p>
        </div>

        <div className="card-sm" style={{ minWidth: 280, alignSelf: 'stretch' }}>
          <p className="label" style={{ marginBottom: '0.55rem' }}>Workspace Context</p>
          <div className="stack-sm">
            <div className="flex-between" style={{ gap: '0.75rem' }}>
              <span className="small-copy">Workspace</span>
              <span className="source-pill">{activeWorkspaceId ? 'Selected' : 'Not selected'}</span>
            </div>
            <div className="flex-between" style={{ gap: '0.75rem' }}>
              <span className="small-copy">Source</span>
              <span className="source-pill">{activeConnectionId ? 'Selected' : 'Not selected'}</span>
            </div>
            {response && (
              <>
                <div className="flex-between" style={{ gap: '0.75rem' }}>
                  <span className="small-copy">Risk</span>
                  <span className={`risk-pill risk-${(riskRating || 'low').toLowerCase()}`}>{riskRating || 'LOW'}</span>
                </div>
                <div className="flex-between" style={{ gap: '0.75rem' }}>
                  <span className="small-copy">Citations</span>
                  <span className="source-pill">{citationCount}</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="grid-4" style={{ gap: '0.75rem' }}>
        {setupSteps.map((step) => (
          <div key={step.label} className="card-sm">
            <p className="label" style={{ marginBottom: '0.25rem' }}>{step.label}</p>
            <p className="small-copy" style={{ lineHeight: 1.5 }}>{step.detail}</p>
          </div>
        ))}
      </div>

      <div className="query-box">
        <div>
          <p className="label">Audit Query</p>
          <form onSubmit={handleSubmit}>
            <div className="query-input-row">
              <input
                className="input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="E.g. Investigate vendor VND-02731 for suspicious payment patterns..."
                disabled={isLoading}
                aria-label="Audit query"
              />
              <button
                type="submit"
                className="btn btn-primary"
                disabled={isLoading || !query.trim()}
                style={{ padding: '0.8rem 1.35rem', fontSize: '0.9rem', flexShrink: 0 }}
              >
                {isLoading ? (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className="step-icon running" style={{ width: 14, height: 14 }}>↻</span>
                    Running...
                  </span>
                ) : (
                  'Start Investigation'
                )}
              </button>
            </div>
          </form>
        </div>

        <div>
          <p className="label" style={{ marginBottom: '0.4rem' }}>Starter Queries</p>
          <div className="query-chips">
            {SAMPLE_QUERIES.map((value) => (
              <button
                key={value}
                className="query-chip"
                type="button"
                onClick={() => handleChip(value)}
                disabled={isLoading}
              >
                {value}
              </button>
            ))}
          </div>
        </div>

        {isLoading && (
          <div>
            <p className="label" style={{ marginBottom: '0.5rem' }}>Running audit workflow...</p>
            <div className="progress-steps">
              {LOADING_STEPS.map((step, index) => {
                const status = index < loadingStepIndex ? 'done' : index === loadingStepIndex ? 'running' : 'waiting';
                return (
                  <div key={step} className={`progress-step ${status}`}>
                    <span className={`step-icon ${status}`}>
                      {status === 'done' ? '✓' : status === 'running' ? '↻' : '◌'}
                    </span>
                    <span>{step}</span>
                    <span style={{ marginLeft: 'auto', fontSize: '0.78rem' }}>
                      {status === 'done' ? 'Done' : status === 'running' ? 'Running...' : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {errorMessage && <FeedbackBanner title="Query Error" message={errorMessage} variant="error" />}

        {(response || isLoading) && (
          <div className="query-meta-bar">
            <span>📄 {citationCount} citations</span>
            <span>⚡ {response?.agents_used.length ?? 0} agents used</span>
            {riskRating && <span>⚠ {riskRating} risk</span>}
            {response && !response.success && <span style={{ color: 'var(--accent-amber)' }}>⚠ Query returned no supported result</span>}
          </div>
        )}
      </div>

      {response ? (
        <AuditResponsePanel response={response} onCitationSelect={handleCitationSelect} />
      ) : !isLoading && !errorMessage ? (
        <div className="card" style={{ padding: '3rem', textAlign: 'center' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem', opacity: 0.3 }}>🔍</div>
          <h2 style={{ fontSize: '1.2rem', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
            Run an audit query to see the investigation
          </h2>
          <p className="body-copy">
            Enter a question above or click one of the quick queries to get started.
          </p>
        </div>
      ) : null}

      <DocumentViewerModal open={isModalOpen} citation={selectedCitation} onClose={() => setIsModalOpen(false)} />
    </div>
  );
}

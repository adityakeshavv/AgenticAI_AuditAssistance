import { type FormEventHandler, useEffect, useMemo, useState } from 'react';
import { AuditResponsePanel } from './AuditResponsePanel';
import { FeedbackBanner } from './FeedbackBanner';
import { DocumentViewerModal } from './DocumentViewerModal';
import { submitAuditQuery } from '../services/auditApi';
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
    if (!isLoading) { setLoadingStepIndex(0); return; }
    const timer = window.setInterval(() => {
      setLoadingStepIndex((c) => Math.min(c + 1, LOADING_STEPS.length - 1));
    }, 480);
    return () => clearInterval(timer);
  }, [isLoading]);

  const citationCount = response?.citations.length ?? 0;
  const riskRating = response?.risk_rating ?? null;

  const handleSubmit: FormEventHandler<HTMLFormElement> = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setIsLoading(true);
    setLoadingStepIndex(0);
    setErrorMessage(null);
    setSelectedCitation(null);
    setIsModalOpen(false);
    try {
      const res = await submitAuditQuery(query);
      setResponse(res);
    } catch (err) {
      setResponse(null);
      setErrorMessage(err instanceof Error ? err.message : 'Unable to run audit query.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChip = (q: string) => { setQuery(q); };

  const handleCitationSelect = (c: CitationRecord) => {
    setSelectedCitation(c);
    setIsModalOpen(true);
  };

  return (
    <div style={{ display: 'grid', gap: '1.5rem', alignItems: 'start' }}>
      {/* Page Header */}
      <div className="flex-between">
        <div>
          <p className="eyebrow" style={{ marginBottom: '0.4rem' }}>Audit Assistant</p>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Investigation Workspace</h1>
          <p className="body-copy" style={{ marginTop: '0.4rem' }}>
            Ask a question, inspect the evidence, and review the resulting audit findings — all in one place.
          </p>
        </div>
        {response && (
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div className={`risk-pill risk-${(riskRating || 'low').toLowerCase()}`} style={{ marginBottom: '0.3rem' }}>
              {riskRating || 'LOW'} Risk
            </div>
            <p className="small-copy">{citationCount} citations · {response.agents_used.length} agents</p>
          </div>
        )}
      </div>

      {/* Query Box */}
      <div className="query-box">
        <div>
          <p className="label">Audit Query</p>
          <form onSubmit={handleSubmit}>
            <div className="query-input-row">
              <input
                className="input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="E.g. Investigate vendor VND-02731 for suspicious payment patterns…"
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
                    Running…
                  </span>
                ) : 'Run Query'}
              </button>
            </div>
          </form>
        </div>

        {/* Quick query chips */}
        <div>
          <p className="label" style={{ marginBottom: '0.4rem' }}>Quick Queries</p>
          <div className="query-chips">
            {SAMPLE_QUERIES.map((q) => (
              <button key={q} className="query-chip" type="button" onClick={() => handleChip(q)} disabled={isLoading}>
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Loading progress */}
        {isLoading && (
          <div>
            <p className="label" style={{ marginBottom: '0.5rem' }}>Running audit workflow…</p>
            <div className="progress-steps">
              {LOADING_STEPS.map((step, i) => {
                const st = i < loadingStepIndex ? 'done' : i === loadingStepIndex ? 'running' : 'waiting';
                return (
                  <div key={step} className={`progress-step ${st}`}>
                    <span className={`step-icon ${st}`}>
                      {st === 'done' ? '✓' : st === 'running' ? '↻' : '○'}
                    </span>
                    <span>{step}</span>
                    <span style={{ marginLeft: 'auto', fontSize: '0.78rem' }}>
                      {st === 'done' ? 'Done' : st === 'running' ? 'Running…' : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Error */}
        {errorMessage && <FeedbackBanner title="Query Error" message={errorMessage} variant="error" />}

        {/* Meta bar */}
        {(response || isLoading) && (
          <div className="query-meta-bar">
            <span>📄 {citationCount} citations</span>
            <span>⚡ {response?.agents_used.length ?? 0} agents used</span>
            {riskRating && <span>⚠ {riskRating} risk</span>}
            {response && !response.success && (
              <span style={{ color: 'var(--accent-amber)' }}>⚠ Query returned no supported result</span>
            )}
          </div>
        )}
      </div>

      {/* Response Panel or Empty State */}
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

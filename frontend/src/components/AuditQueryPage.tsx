import { type FormEvent, useState } from 'react';
import { AuditResponsePanel } from './AuditResponsePanel';
import { DocumentViewerModal } from './DocumentViewerModal';
import { submitAuditQuery } from '../services/auditApi';
import type { AuditResponse, CitationRecord } from '../types/audit';

export function AuditQueryPage() {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState<AuditResponse | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<CitationRecord | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const citationCount = response?.citations.length ?? 0;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setErrorMessage(null);
    setSelectedCitation(null);
    setIsModalOpen(false);

    try {
      const apiResponse = await submitAuditQuery(query);
      setResponse(apiResponse);
    } catch (error) {
      setResponse(null);
      setErrorMessage(error instanceof Error ? error.message : 'Unable to run audit query.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCitationSelect = (citation: CitationRecord) => {
    setSelectedCitation(citation);
    setIsModalOpen(true);
  };

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Audit Assistant</p>
          <h1>Evidence Viewer</h1>
          <p className="hero-copy">
            Review audit findings, supporting evidence, and citations from a single transparent workflow.
          </p>
        </div>
      </header>

      <main className="page-grid">
        <section className="query-card panel">
          <form onSubmit={handleSubmit} className="query-form">
            <label htmlFor="audit-query">Audit query</label>
            <div className="query-row">
              <input
                id="audit-query"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Enter an audit question"
                disabled={isLoading}
              />
              <button type="submit" disabled={isLoading}>
                {isLoading ? 'Running...' : 'Run query'}
              </button>
            </div>
          </form>
          {isLoading ? <div className="query-meta">Running audit query...</div> : null}
          {errorMessage ? (
            <div className="section-block">
              <p className="section-label">Error</p>
              <p className="body-copy">{errorMessage}</p>
            </div>
          ) : null}
          <div className="query-meta">
            <span>{citationCount} citations</span>
            <span>{response ? `${response.risk_rating} risk` : 'Awaiting results'}</span>
            <span>{response ? response.agents_used.join(' | ') : 'No agents yet'}</span>
          </div>
        </section>

        {response ? (
          <AuditResponsePanel response={response} onCitationSelect={handleCitationSelect} />
        ) : (
          <section className="panel response-panel">
            <div className="section-block">
              <p className="section-label">Finding</p>
              <h2>Run an audit query to see the response</h2>
              <p className="body-copy">The backend response will appear here once the query completes.</p>
            </div>
          </section>
        )}
      </main>

      <DocumentViewerModal
        open={isModalOpen}
        citation={selectedCitation}
        onClose={() => setIsModalOpen(false)}
      />
    </div>
  );
}

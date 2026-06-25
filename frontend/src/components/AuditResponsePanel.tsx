import { useMemo, useState } from 'react';
import type { AuditResponse, CitationRecord } from '../types/audit';
import { CitationList } from './CitationList';
import { TraceabilityPanel } from './TraceabilityPanel';

interface AuditResponsePanelProps {
  response: AuditResponse;
  onCitationSelect: (citation: CitationRecord) => void;
}

type PanelTab = 'summary' | 'evidence' | 'traceability';

function textOrFallback(value: string | undefined, fallback: string) {
  return value && value.trim() ? value.trim() : fallback;
}

function summarizeEvidence(response: AuditResponse) {
  const parts: string[] = [];
  const drivers = response.risk_drivers.slice(0, 3);

  if (response.risk_score || response.risk_rating) {
    parts.push(`Risk assessment returned ${response.risk_rating} with score ${response.risk_score}.`);
  }
  if (drivers.length > 0) {
    parts.push(`Top risk drivers: ${drivers.join('; ')}.`);
  }
  if (response.key_findings.length > 0) {
    parts.push(`${response.key_findings.length} key finding${response.key_findings.length === 1 ? '' : 's'} were returned.`);
  }
  if (response.citations.length > 0) {
    parts.push(`${response.citations.length} citation${response.citations.length === 1 ? '' : 's'} support the response.`);
  }
  if (response.supporting_documents.length > 0) {
    parts.push(`${response.supporting_documents.length} supporting document${response.supporting_documents.length === 1 ? '' : 's'} were linked.`);
  }
  if (response.document_intelligence_summary) {
    parts.push(response.document_intelligence_summary);
  }
  return parts.join(' ');
}

function summarizeInvestigation(response: AuditResponse) {
  if (textOrFallback(response.investigation_summary, '') !== '') {
    return response.investigation_summary;
  }

  const subject = response.entity_type || response.intent.intent || 'audit query';
  const findings =
    response.key_findings.length > 0
      ? response.key_findings.slice(0, 2).join('; ')
      : 'no explicit key findings were returned';
  const docs =
    response.supporting_documents.length > 0
      ? `${response.supporting_documents.length} supporting document${response.supporting_documents.length === 1 ? '' : 's'} were attached`
      : 'no supporting documents were attached';

  return `This ${subject} was reviewed through the audit workflow. ${findings}. ${docs}.`;
}

function buildKeyFindings(response: AuditResponse) {
  const findings = response.key_findings.filter((finding) => finding !== response.finding.title);
  if (findings.length > 0) {
    return findings;
  }
  if (textOrFallback(response.finding.summary, '') !== '') {
    return [response.finding.summary];
  }
  return [];
}

function buildSupportingDocumentSummary(document: Record<string, unknown>) {
  const parts: string[] = [];

  if (document.document_id) {
    parts.push(String(document.document_id));
  }
  if (document.file_name) {
    parts.push(String(document.file_name));
  }
  if (document.page_number !== undefined && document.page_number !== null) {
    parts.push(`Page ${String(document.page_number)}`);
  }
  if (document.section_title) {
    parts.push(String(document.section_title));
  }
  if (document.linked_transaction) {
    parts.push(`Linked transaction ${String(document.linked_transaction)}`);
  }
  if (document.reason_selected) {
    parts.push(String(document.reason_selected));
  }

  return parts.join(' - ');
}

function buildEvidenceSummaryItems(items: Record<string, unknown>[]) {
  return items.map((item, index) => {
    const doc = item as Record<string, unknown>;
    return {
      key: String(doc.document_id ?? doc.chunk_id ?? index),
      title: String(doc.title ?? doc.document_id ?? `Evidence ${index + 1}`),
      summary: String(
        doc.summary ??
          doc.reason_selected ??
          doc.citation_text ??
          doc.content_snippet ??
          'No evidence details available.',
      ),
    };
  });
}

function buildWorkflowSteps(agents: string[]) {
  return agents.length > 0 ? agents.map((agent) => agent.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())) : [];
}

function buildAgentOutput(agent: string, response: AuditResponse) {
  const lower = agent.toLowerCase();
  if (lower.includes('transaction')) {
    return `Produced ${response.investigation_metrics.transactions_reviewed ?? response.structured_evidence.length} structured records.`;
  }
  if (lower.includes('document')) {
    return `Linked ${response.supporting_documents.length} supporting document${response.supporting_documents.length === 1 ? '' : 's'}.`;
  }
  if (lower.includes('finding')) {
    return 'Generated the final audit finding.';
  }
  return 'Produced audit evidence used in the response.';
}

export function AuditResponsePanel({ response, onCitationSelect }: AuditResponsePanelProps) {
  const [activeTab, setActiveTab] = useState<PanelTab>('summary');

  const findingTitle = response.finding.title || response.key_findings[0] || 'Audit observation';
  const findingSummary = textOrFallback(
    response.finding.summary ||
      response.investigation_summary ||
      response.transaction_summary ||
      response.vendor_summary ||
      response.final_response,
    'No summary provided.',
  );
  const findingCategory = response.finding.category || response.entity_type || 'Audit observation';
  const findingSeverity = response.finding.severity || response.risk_rating || 'LOW';
  const recommendation = textOrFallback(
    response.finding.recommendation || response.recommendations[0],
    'No recommendation available.',
  );
  const keyFindings = buildKeyFindings(response);
  const workflowSteps = buildWorkflowSteps(response.agents_used);
  const evidenceSummary = summarizeEvidence(response);
  const investigationSummary = summarizeInvestigation(response);
  const evidenceMetrics = useMemo(
    () => [
      ['Risk Score', response.risk_score],
      ['Citations Returned', response.citations.length],
      ['Supporting Documents', response.supporting_documents.length],
      ['Structured Evidence', response.structured_evidence.length],
      ['Document Evidence', response.document_evidence.length],
    ] as const,
    [response],
  );
  const supportingDocuments = response.supporting_documents.map((item, index) => ({
    key: String((item as Record<string, unknown>).document_id ?? index),
    value: item as Record<string, unknown>,
  }));
  const topEvidence = buildEvidenceSummaryItems(
    response.top_supporting_evidence.length > 0 ? response.top_supporting_evidence : response.supporting_documents,
  );

  return (
    <section className="panel response-panel">
      <nav className="section-block" aria-label="Audit response tabs">
        <div className="query-meta">
          <button type="button" className="modal-close" onClick={() => setActiveTab('summary')}>
            Summary
          </button>
          <button type="button" className="modal-close" onClick={() => setActiveTab('evidence')}>
            Evidence
          </button>
          <button type="button" className="modal-close" onClick={() => setActiveTab('traceability')}>
            Traceability
          </button>
        </div>
      </nav>

      {activeTab === 'summary' ? (
        <>
          <section className="section-block">
            <p className="section-label">Executive Summary</p>
            <div className="section-grid">
              <div className="metric-card">
                <p className="section-label">Finding</p>
                <h2>{findingTitle}</h2>
                <p className="body-copy">{findingSummary}</p>
                <p className="small-copy">
                  <strong>Category:</strong> {findingCategory} <br />
                  <strong>Severity:</strong> {findingSeverity}
                </p>
              </div>
              <div className="metric-card">
                <p className="section-label">Risk Rating</p>
                <div className={`risk-pill risk-${response.risk_rating.toLowerCase()}`}>{response.risk_rating}</div>
                <p className="small-copy">Risk score {response.risk_score}</p>
              </div>
              <div className="metric-card">
                <p className="section-label">Recommendation</p>
                <p className="body-copy">{recommendation}</p>
              </div>
            </div>
          </section>

          {response.risk_drivers.length > 0 ? (
            <section className="section-block">
              <p className="section-label">Risk Drivers</p>
              <ul className="list-block">
                {response.risk_drivers.map((driver) => (
                  <li key={driver}>{driver}</li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="section-block">
            <p className="section-label">Metrics</p>
            <div className="section-grid">
              {evidenceMetrics.map(([label, value]) => (
                <div key={label} className="metric-card">
                  <p className="section-label">{label}</p>
                  <h3>{value}</h3>
                </div>
              ))}
            </div>
          </section>

          <section className="section-block">
            <p className="section-label">Agent Workflow</p>
            {workflowSteps.length > 0 ? (
              <ol className="list-block">
                {workflowSteps.map((agent, index) => (
                  <li key={agent}>
                    <strong>{agent}</strong>
                    <p className="small-copy">{buildAgentOutput(response.agents_used[index] || agent, response)}</p>
                    {index < workflowSteps.length - 1 ? <div className="small-copy">↓</div> : null}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="body-copy">No agents were returned.</p>
            )}
          </section>

          <div className="section-grid">
            <div className="metric-card">
              <p className="section-label">Evidence Summary</p>
              <p className="body-copy">{evidenceSummary}</p>
            </div>

            <div className="metric-card">
              <p className="section-label">Investigation Summary</p>
              <p className="body-copy">{investigationSummary}</p>
            </div>

            <div className="metric-card">
              <p className="section-label">Document Intelligence</p>
              <p className="body-copy">{response.document_intelligence_summary || 'No document intelligence was returned.'}</p>
            </div>
          </div>
        </>
      ) : null}

      {activeTab === 'evidence' ? (
        <>
          <div className="section-grid">
            <div className="metric-card">
              <p className="section-label">Supporting Documents</p>
              {supportingDocuments.length > 0 ? (
                <div className="supporting-document-list">
                  {supportingDocuments.map(({ key, value }) => (
                    <article key={key} className="supporting-document-item">
                      <p className="supporting-document-title">
                        {String(value.document_id ?? 'Unknown document')}
                        {value.file_name ? <span> - {String(value.file_name)}</span> : null}
                      </p>
                      <p className="supporting-document-detail">{buildSupportingDocumentSummary(value)}</p>
                      {value.content_snippet || value.citation_text ? (
                        <p className="supporting-document-snippet">
                          {String(value.content_snippet ?? value.citation_text)}
                        </p>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <p className="body-copy">No supporting documents were returned.</p>
              )}
            </div>

            <div className="metric-card">
              <p className="section-label">Top Supporting Evidence</p>
              {topEvidence.length > 0 ? (
                <div className="supporting-document-list">
                  {topEvidence.map((item) => (
                    <article key={item.key} className="supporting-document-item">
                      <p className="supporting-document-title">{item.title}</p>
                      <p className="supporting-document-snippet">{item.summary}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="body-copy">No top supporting evidence was returned.</p>
              )}
            </div>
          </div>

          <section className="section-block">
            <p className="section-label">Citations</p>
            <CitationList citations={response.citations} onSelect={onCitationSelect} />
          </section>
        </>
      ) : null}

      {activeTab === 'traceability' ? <TraceabilityPanel response={response} /> : null}
    </section>
  );
}

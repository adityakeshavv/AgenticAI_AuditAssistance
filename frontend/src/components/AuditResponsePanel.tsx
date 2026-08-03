import { useMemo, useState } from 'react';
import type { AuditResponse, CitationRecord } from '../types/audit';
import { CitationList } from './CitationList';
import { LangfusePanel } from './LangfusePanel';
import { TraceabilityPanel } from './TraceabilityPanel';
import { ValidationSummary } from './ValidationSummary';

interface Props {
  response: AuditResponse;
  onCitationSelect: (c: CitationRecord) => void;
}

type Tab = 'summary' | 'evidence' | 'traceability' | 'langfuse';

function txt(v: string | undefined, fallback: string) {
  return v?.trim() || fallback;
}

function prettyLabel(v: string) {
  return v.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()).trim();
}

function RiskScoreBar({ score, rating }: { score: number; rating: string }) {
  const color =
    rating === 'HIGH'
      ? 'var(--accent-red)'
      : rating === 'MEDIUM'
        ? 'var(--accent-amber)'
        : 'var(--accent-green)';

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: '0.3rem' }}>
        <span className="small-copy">Risk Score</span>
        <strong style={{ fontSize: '1.1rem', color }}>{score}</strong>
      </div>
      <div className="risk-score-bar">
        <div className="risk-score-fill" style={{ width: `${Math.min(score, 100)}%`, background: color }} />
      </div>
    </div>
  );
}

export function AuditResponsePanel({ response, onCitationSelect }: Props) {
  const [tab, setTab] = useState<Tab>('summary');

  const findingTitle = response.finding.title || response.key_findings[0] || 'Audit Observation';
  const findingSummary = txt(
    response.finding.summary ||
      response.investigation_summary ||
      response.transaction_summary ||
      response.vendor_summary ||
      response.final_response,
    'No summary provided.'
  );
  const findingCategory = response.finding.category || response.entity_type || 'Audit Observation';
  const findingSeverity = response.finding.severity || response.risk_rating || 'LOW';
  const recommendation = txt(response.finding.recommendation || response.recommendations[0], 'No recommendation available.');
  const keyFindings = response.key_findings.filter((f) => f !== response.finding.title);
  const workflowSteps = response.agents_used.length > 0 ? response.agents_used.map(prettyLabel) : [];
  const evaluation = response.evaluation;

  const evidenceMetrics = useMemo(
    () => [
      { label: 'Citations', value: response.citations.length, color: 'var(--accent-blue)' },
      { label: 'Supporting Docs', value: response.supporting_documents.length, color: 'var(--accent-cyan)' },
      { label: 'Structured Evidence', value: response.structured_evidence.length, color: 'var(--accent-violet)' },
      { label: 'Document Evidence', value: response.document_evidence.length, color: 'var(--accent-green)' },
      {
        label: 'Transactions Reviewed',
        value: response.investigation_metrics?.transactions_reviewed ?? response.structured_evidence.length,
        color: 'var(--accent-amber)',
      },
    ],
    [response]
  );

  return (
    <div className="response-panel">
      <div className="response-panel-header">
        <div className="flex-between" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <p className="eyebrow" style={{ marginBottom: '0.3rem' }}>
              Investigation Result
            </p>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700 }}>{findingTitle}</h2>
          </div>
          <div className="flex-row" style={{ gap: '0.6rem', flexShrink: 0 }}>
            <span className={`risk-pill risk-${(response.risk_rating || 'low').toLowerCase()}`}>{response.risk_rating || 'LOW'}</span>
            <span className="small-copy" style={{ color: 'var(--text-muted)' }}>
              Score: {response.risk_score}
            </span>
          </div>
        </div>

        <div className="tab-bar" style={{ marginTop: '0.5rem', marginBottom: '-1px' }}>
          {(['summary', 'evidence', 'traceability'] as Tab[]).map((t) => (
            <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
              {t === 'summary' ? 'Summary' : t === 'evidence' ? 'Evidence' : 'Traceability'}
            </button>
          ))}
          <button className={`tab-btn${tab === 'langfuse' ? ' active' : ''}`} onClick={() => setTab('langfuse')}>
            Langfuse
          </button>
        </div>
      </div>

      <div className="response-panel-body">
        {tab === 'summary' && (
          <div className="stack">
            <div className="grid-3" style={{ gap: '1rem' }}>
              <div className="card-sm" style={{ gridColumn: 'span 2' }}>
                <p className="label">Finding</p>
                <h3 style={{ marginBottom: '0.6rem', fontSize: '1rem' }}>{findingTitle}</h3>
                <p className="body-copy">{findingSummary}</p>
                <div className="flex-row" style={{ marginTop: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <span className="source-pill">Category: {findingCategory}</span>
                  <span className={`risk-pill risk-${findingSeverity.toLowerCase()}`}>Severity: {findingSeverity}</span>
                </div>
              </div>

              <div className="card-sm">
                <p className="label">Risk Assessment</p>
                <div
                  className={`risk-pill risk-${(response.risk_rating || 'low').toLowerCase()}`}
                  style={{ marginBottom: '0.75rem', fontSize: '1rem', fontWeight: 800 }}
                >
                  {response.risk_rating || 'LOW'}
                </div>
                <RiskScoreBar score={response.risk_score} rating={response.risk_rating || 'LOW'} />
              </div>
            </div>

            <div className="card-sm" style={{ borderLeft: '3px solid var(--accent-blue)' }}>
              <p className="label">Recommendation</p>
              <p className="body-copy">{recommendation}</p>
            </div>

            <div>
              <p className="label" style={{ marginBottom: '0.75rem' }}>
                Evidence Metrics
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.75rem' }}>
                {evidenceMetrics.map(({ label, value, color }) => (
                  <div key={label} className="card-sm" style={{ textAlign: 'center', borderTop: `2px solid ${color}` }}>
                    <div style={{ fontSize: '1.6rem', fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
                    <div className="small-copy" style={{ marginTop: '0.25rem' }}>
                      {label}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {keyFindings.length > 0 && (
              <div className="card-sm">
                <p className="label">Key Findings</p>
                <div className="stack-sm" style={{ marginTop: '0.4rem' }}>
                  {keyFindings.map((f, i) => (
                    <div key={i} className="flex-row" style={{ alignItems: 'flex-start', gap: '0.65rem' }}>
                      <span style={{ color: 'var(--accent-blue)', fontSize: '0.7rem', marginTop: '0.15rem', flexShrink: 0 }}>•</span>
                      <span className="body-copy">{f}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {response.risk_drivers.length > 0 && (
              <div className="card-sm">
                <p className="label">Risk Drivers</p>
                <div className="stack-sm" style={{ marginTop: '0.4rem' }}>
                  {response.risk_drivers.map((d) => (
                    <div key={d} className="flex-row" style={{ alignItems: 'flex-start', gap: '0.65rem' }}>
                      <span style={{ color: 'var(--accent-red)', fontSize: '0.7rem', marginTop: '0.15rem', flexShrink: 0 }}>•</span>
                      <span className="body-copy">{d}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {workflowSteps.length > 0 && (
              <div className="card-sm">
                <p className="label">Agent Workflow Executed</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.5rem', alignItems: 'center' }}>
                  {workflowSteps.map((step, i) => (
                    <span key={step} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <span className="badge badge-completed">{step}</span>
                      {i < workflowSteps.length - 1 && <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>→</span>}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="grid-3" style={{ gap: '1rem' }}>
              {response.investigation_summary && (
                <div className="card-sm">
                  <p className="label">Investigation Summary</p>
                  <p className="body-copy">{response.investigation_summary}</p>
                </div>
              )}
              {response.transaction_summary && (
                <div className="card-sm">
                  <p className="label">Transaction Summary</p>
                  <p className="body-copy">{response.transaction_summary}</p>
                </div>
              )}
              {response.document_intelligence_summary && (
                <div className="card-sm">
                  <p className="label">Document Intelligence</p>
                  <p className="body-copy">{response.document_intelligence_summary}</p>
                </div>
              )}
            </div>

            {evaluation && (
              <div className="card-sm">
                <p className="label">Response Evaluation</p>
                <div className="stack-sm" style={{ marginTop: '0.5rem' }}>
                  {[
                    ['Retrieval Relevance', evaluation.retrieval_relevance],
                    ['Grounding Quality', evaluation.grounding_quality],
                    ['Faithfulness', evaluation.faithfulness],
                    ['Citation Coverage', evaluation.citation_coverage],
                  ]
                    .filter(([, v]) => v)
                    .map(([label, val]) => (
                      <div key={label as string} className="eval-row">
                        <span className="small-copy">{label}</span>
                        <span className="eval-value">{val || '—'}</span>
                      </div>
                    ))}
                  {evaluation.summary && (
                    <p className="body-copy" style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border)' }}>
                      {evaluation.summary}
                    </p>
                  )}
                </div>
              </div>
            )}

            <ValidationSummary response={response} />
          </div>
        )}

        {tab === 'evidence' && (
          <div className="stack">
            <div>
              <p className="label" style={{ marginBottom: '0.6rem' }}>
                Supporting Documents ({response.supporting_documents.length})
              </p>
              {response.supporting_documents.length > 0 ? (
                <div className="doc-list">
                  {response.supporting_documents.map((doc, i) => {
                    const d = doc as Record<string, unknown>;
                    const exp = (d.selection_explanation as Record<string, unknown> | undefined) ?? {};
                    const contentSnippet = String(d.content_snippet ?? d.citation_text ?? '');
                    const selectionReason = String(d.reason_selected ?? exp.selection_reason ?? '');
                    const supportsText = String(d.supports ?? exp.supports ?? '');

                    return (
                      <div key={String(d.document_id ?? i)} className="doc-item">
                        <div className="flex-between">
                          <span className="doc-item-title">
                            {String(d.document_id ?? 'Unknown document')}
                            {d.file_name ? ` | ${String(d.file_name)}` : ''}
                          </span>
                          {d.relevance_score != null && (
                            <span className="citation-score">{(Number(d.relevance_score) * 100).toFixed(0)}% relevance</span>
                          )}
                        </div>
                        <div className="doc-item-detail">
                          {[d.page_number != null && `Page ${d.page_number}`, d.section_title, d.linked_transaction && `Linked: ${d.linked_transaction}`]
                            .filter(Boolean)
                            .join(' | ')}
                        </div>
                        {contentSnippet && <p className="doc-item-snippet">{contentSnippet}</p>}
                        {(selectionReason || supportsText) && (
                          <div style={{ marginTop: '0.4rem', paddingTop: '0.4rem', borderTop: '1px solid var(--border)' }}>
                            {selectionReason && (
                              <p className="small-copy">
                                <strong>Why selected:</strong> {selectionReason}
                              </p>
                            )}
                            {supportsText && (
                              <p className="small-copy">
                                <strong>Supports:</strong> {supportsText}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="body-copy">No supporting documents were returned.</p>
              )}
            </div>

            {response.top_supporting_evidence.length > 0 && (
              <div>
                <p className="label" style={{ marginBottom: '0.6rem' }}>
                  Top Evidence ({response.top_supporting_evidence.length})
                </p>
                <div className="doc-list">
                  {response.top_supporting_evidence.map((item, i) => {
                    const d = item as Record<string, unknown>;
                    const documentTypeText = String(d.document_type ?? '');
                    const documentCategoryText = String(d.document_category ?? '');
                    const relevanceText = d.relevance_score != null ? `${(Number(d.relevance_score) * 100).toFixed(0)}% relevance` : '';
                    return (
                      <div key={String(d.document_id ?? d.chunk_id ?? i)} className="evidence-card">
                        <div className="evidence-card-title">{String(d.title ?? d.document_id ?? `Evidence ${i + 1}`)}</div>
                        <div className="evidence-card-meta">
                          {documentTypeText && <span>{documentTypeText}</span>}
                          {documentCategoryText && <span>{documentCategoryText}</span>}
                          {relevanceText && <span>{relevanceText}</span>}
                        </div>
                        {String(d.content_snippet ?? d.citation_text ?? d.reason_selected ?? '') && (
                          <p className="evidence-card-snippet">{String(d.content_snippet ?? d.citation_text ?? d.reason_selected ?? '')}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {response.recommendations.length > 0 && (
              <div className="card-sm">
                <p className="label">Recommendations ({response.recommendations.length})</p>
                <div className="stack-sm" style={{ marginTop: '0.5rem' }}>
                  {response.recommendations.map((rec, i) => (
                    <div key={i} className="flex-row" style={{ alignItems: 'flex-start', gap: '0.6rem' }}>
                      <span
                        style={{
                          background: 'rgba(59,130,246,0.15)',
                          color: 'var(--accent-blue)',
                          borderRadius: '50%',
                          width: 20,
                          height: 20,
                          display: 'grid',
                          placeItems: 'center',
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        {i + 1}
                      </span>
                      <span className="body-copy">{rec}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <p className="label" style={{ marginBottom: '0.6rem' }}>
                Citations ({response.citations.length})
              </p>
              <CitationList citations={response.citations} onSelect={onCitationSelect} />
            </div>
          </div>
        )}

        {tab === 'traceability' && <TraceabilityPanel response={response} />}
        {tab === 'langfuse' && <LangfusePanel response={response} />}
      </div>
    </div>
  );
}

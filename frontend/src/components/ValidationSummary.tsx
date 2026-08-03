import type { AuditResponse } from '../types/audit';

interface ValidationSummaryProps {
  response: AuditResponse;
}

function hasEvaluation(response: AuditResponse) {
  return Boolean(
    response.evaluation &&
      (response.evaluation.retrieval_relevance ||
        response.evaluation.grounding_quality ||
        response.evaluation.faithfulness ||
        response.evaluation.citation_coverage ||
        response.evaluation.summary)
  );
}

export function ValidationSummary({ response }: ValidationSummaryProps) {
  if (!hasEvaluation(response)) {
    return null;
  }

  const evaluation = response.evaluation!;
  const fields = [
    ['Retrieval Relevance', evaluation.retrieval_relevance],
    ['Grounding Quality', evaluation.grounding_quality],
    ['Faithfulness', evaluation.faithfulness],
    ['Citation Coverage', evaluation.citation_coverage],
  ].filter(([, value]) => Boolean(value));

  return (
    <div className="metric-card">
      <p className="section-label">Validation</p>
      <p className="body-copy">Quality checks that describe how well the response is grounded in retrieved evidence.</p>
      <div className="stack-sm" style={{ marginTop: '0.65rem' }}>
        {fields.map(([label, value]) => (
          <div key={label as string} className="eval-row">
            <span className="small-copy">{label}</span>
            <span className="eval-value">{value as string}</span>
          </div>
        ))}
      </div>
      {evaluation.summary && (
        <p className="body-copy" style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border)' }}>
          {evaluation.summary}
        </p>
      )}
    </div>
  );
}

import type { AuditResponse } from '../types/audit';

interface ValidationSummaryProps {
  response: AuditResponse;
}

export function ValidationSummary({ response }: ValidationSummaryProps) {
  if (!response.traceability || response.traceability.reasoning_path.length === 0) {
    return null;
  }

  return (
    <div className="metric-card">
      <p className="section-label">Validation</p>
      <p className="body-copy">Validation details are not currently surfaced by the backend response contract.</p>
      <ul className="list-block">
        <li>
          <strong>Status:</strong> Not available
        </li>
        <li>
          <strong>Checks:</strong> Hidden until validation output is added to the API contract
        </li>
      </ul>
    </div>
  );
}

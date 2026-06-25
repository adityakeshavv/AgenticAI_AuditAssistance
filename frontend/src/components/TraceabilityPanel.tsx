import type { AuditResponse } from '../types/audit';
import { ReasoningTimeline } from './ReasoningTimeline';
import { SourceTraceCard } from './SourceTraceCard';

interface TraceabilityPanelProps {
  response: AuditResponse;
}

function prettifyAgentName(agent: string) {
  return agent
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function buildAgentOutput(agent: string, response: AuditResponse) {
  const lower = agent.toLowerCase();
  if (lower.includes('transaction')) {
    return `Produced ${response.investigation_metrics.transactions_reviewed ?? 0} reviewed transactions.`;
  }
  if (lower.includes('document')) {
    return `Linked ${response.supporting_documents.length} supporting document${response.supporting_documents.length === 1 ? '' : 's'}.`;
  }
  return `Produced audit evidence used in the response.`;
}

function buildEvidenceFlow(response: AuditResponse) {
  return [
    ['Structured Evidence Count', response.structured_evidence.length],
    ['Document Evidence Count', response.document_evidence.length],
    ['Citations Generated', response.citations.length],
    ['Finding Produced', response.finding.title || 'Audit finding'],
  ] as const;
}

export function TraceabilityPanel({ response }: TraceabilityPanelProps) {
  const workflowAgents = response.agents_used.length > 0 ? response.agents_used : response.traceability.agents_invoked;
  const sources = response.sources.length > 0 ? response.sources : response.traceability.sources_used;
  const evidenceFlow = buildEvidenceFlow(response);

  return (
    <div className="section-block">
      <p className="section-label">Traceability</p>

      <div className="section-block">
        <p className="section-label">Explainability Summary</p>
        <p className="body-copy">
          This finding was generated using {workflowAgents.length > 0 ? workflowAgents.join(' and ') : 'the audit workflow'}.
          {` ${response.structured_evidence.length} structured records and ${response.document_evidence.length} document evidence item${
            response.document_evidence.length === 1 ? '' : 's'
          } contributed to the result.`}
          {` The response was supported by ${response.citations.length} citation${response.citations.length === 1 ? '' : 's'}.`}
        </p>
      </div>

      <div className="section-block">
        <p className="section-label">Agent Participation</p>
        {workflowAgents.length > 0 ? (
          <div className="supporting-document-list">
            {workflowAgents.map((agent) => (
              <article key={agent} className="supporting-document-item">
                <p className="supporting-document-title">{prettifyAgentName(agent)}</p>
                <p className="supporting-document-detail">{buildAgentOutput(agent, response)}</p>
                <p className="supporting-document-snippet">{response.traceability.agent_selection_reasoning[0] || 'Agent participated in the audit workflow.'}</p>
              </article>
            ))}
          </div>
        ) : (
          <p className="body-copy">No agent participation details were returned.</p>
        )}
      </div>

      <div className="section-block">
        <p className="section-label">Source Traceability</p>
        {sources.length > 0 ? (
          <div className="supporting-document-list">
            {sources.map((source) => (
              <SourceTraceCard key={source} source={source} />
            ))}
          </div>
        ) : (
          <p className="body-copy">No source traceability data was returned.</p>
        )}
      </div>

      <div className="section-block">
        <p className="section-label">Evidence Flow</p>
        <ol className="list-block">
          {evidenceFlow.map(([label, value], index) => (
            <li key={label}>
              <strong>{label}:</strong> {value as string | number}
              {index < evidenceFlow.length - 1 ? <div className="small-copy">↓</div> : null}
            </li>
          ))}
        </ol>
      </div>

      <div className="section-block">
        <p className="section-label">Reasoning Timeline</p>
        <ReasoningTimeline steps={response.reasoning.length > 0 ? response.reasoning : response.traceability.reasoning_path} />
      </div>

    </div>
  );
}

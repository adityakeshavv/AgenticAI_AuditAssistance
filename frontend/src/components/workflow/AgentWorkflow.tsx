import { useMemo, useState } from 'react';
import type { AuditResponse } from '../../types/audit';
import { WorkflowNode, type WorkflowStatus } from './WorkflowNode';
import { WorkflowEdge } from './WorkflowEdge';
import { AgentExecutionPanel, type WorkflowNodeModel } from './AgentExecutionPanel';

interface Props { response: AuditResponse; }

const PIPELINE_DEFINITIONS: Record<string, { description: string; purpose: string }> = {
  'Intent Extraction': {
    description: 'Parses the raw query into structured intent object.',
    purpose: 'Converts the natural-language audit question into a machine-readable intent: entity type, entity ID, query type, and time range.',
  },
  'Investigation Planner': {
    description: 'Routes intent to the appropriate audit agents.',
    purpose: 'Analyzes the intent and decides which downstream agents need to run, their order, and their parameters.',
  },
  'Transaction Agent': {
    description: 'Retrieves structured transaction records from the database.',
    purpose: 'Queries PostgreSQL for matching transactions, applying filters for entity, date range, and flag status.',
  },
  'Vendor Agent': {
    description: 'Retrieves and analyses vendor profile data.',
    purpose: 'Looks up vendor records, risk scores, payment history, and compliance flags.',
  },
  'Compliance Agent': {
    description: 'Checks applicable policy and regulatory rules.',
    purpose: 'Evaluates whether the retrieved data violates company policy, regulatory thresholds, or known fraud patterns.',
  },
  'Approval Agent': {
    description: 'Validates approval chains and authority levels.',
    purpose: 'Checks whether transactions were properly approved within authorization limits.',
  },
  'Document Retrieval Agent': {
    description: 'Performs semantic search over the enterprise document store.',
    purpose: 'Retrieves supporting evidence documents via embedding similarity, matching policy files, emails, and reports.',
  },
  'Evidence Aggregator': {
    description: 'Merges structured and document evidence into a unified payload.',
    purpose: 'Reconciles evidence from all agents, resolves conflicts, deduplicates, and ranks by relevance.',
  },
  'Response Composer': {
    description: 'Produces the final audit finding and recommendations.',
    purpose: 'Synthesises the aggregated evidence into a human-readable finding with risk rating, key observations, and actionable recommendations.',
  },
  'Validation': {
    description: 'Validates the response for faithfulness and completeness.',
    purpose: 'Runs automated evaluation: checks grounding, citation coverage, and retrieval relevance before returning the response.',
  },
};

function pretty(v: string) {
  return v.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()).trim();
}
function deriveStatus(agent: string, execMeta: Record<string, string>[]): WorkflowStatus {
  const entry = execMeta.find((e) => pretty(String(e.agent || '')) === agent);
  if (!entry) return 'Completed';
  const s = String(entry.status || '').toLowerCase();
  if (s.includes('fail')) return 'Failed';
  if (s.includes('skip')) return 'Skipped';
  return 'Completed';
}

export function AgentWorkflow({ response }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const execMeta = (response.execution_metadata || response.traceability.execution_metadata || []) as Record<string, string>[];

  const nodes: WorkflowNodeModel[] = useMemo(() => {
    const agentNames = response.agents_used.map(pretty);
    const full = agentNames.length > 0
      ? agentNames
      : ['Intent Extraction', 'Investigation Planner', 'Transaction Agent', 'Document Retrieval Agent', 'Evidence Aggregator', 'Response Composer'];

    return full.map((name, i) => {
      const def = PIPELINE_DEFINITIONS[name] ?? {
        description: `Handles audit processing step ${i + 1}.`,
        purpose: `Executes the ${name} phase of the audit pipeline.`,
      };
      const status = deriveStatus(name, execMeta);
      const meta = execMeta.find((e) => pretty(String(e.agent || '')) === name);
      const reason = String(meta?.reason_selected ?? 'Planner-selected execution step.');

      return {
        id: `node-${i}`,
        label: name,
        status,
        description: def.description,
        purpose: def.purpose,
        input: reason,
        output: i === full.length - 1
          ? `Final audit finding (risk: ${response.risk_rating ?? 'N/A'}, score: ${response.risk_score})`
          : `Processed output forwarded to ${full[i + 1] ?? 'next step'}`,
        summary: def.purpose,
        evidenceCount: i === full.length - 1
          ? response.structured_evidence.length + response.document_evidence.length
          : undefined,
        sourceCount: i === full.length - 1 ? response.sources.length : undefined,
      };
    });
  }, [response, execMeta]);

  const selectedNode = nodes.find((n) => n.id === selectedId) ?? null;

  return (
    <div className="card-sm">
      <p className="label" style={{ marginBottom: '0.75rem' }}>Interactive Agent Workflow</p>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.1fr', gap: '1.25rem', alignItems: 'start' }}>
        {/* Pipeline steps */}
        <div style={{ display: 'grid', gap: 0 }}>
          {nodes.map((node, i) => (
            <div key={node.id}>
              <WorkflowNode
                label={node.label}
                description={node.description}
                status={node.status}
                selected={selectedId === node.id}
                onSelect={() => setSelectedId(selectedId === node.id ? null : node.id)}
              />
              {i < nodes.length - 1 && <WorkflowEdge count={i + 2} />}
            </div>
          ))}
        </div>

        {/* Detail panel */}
        <AgentExecutionPanel node={selectedNode} response={response} />
      </div>
    </div>
  );
}

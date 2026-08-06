import { useMemo, useState } from 'react';
import { FeedbackBanner } from './FeedbackBanner';
import { fetchKnowledgeGraph } from '../services/knowledgeGraphApi';
import type {
  KnowledgeGraphEdgeRecord,
  KnowledgeGraphEntityType,
  KnowledgeGraphNodeRecord,
  KnowledgeGraphResponse,
} from '../types/audit';

const ENTITY_TYPE_OPTIONS: Array<{ value: KnowledgeGraphEntityType; label: string; sample: string }> = [
  { value: 'vendor', label: 'Vendor', sample: 'VND-02731' },
  { value: 'transaction', label: 'Transaction', sample: 'TXN-C8972378' },
  { value: 'contract', label: 'Contract', sample: 'CON-00123' },
  { value: 'compliance_record', label: 'Compliance Record', sample: 'COMP-00101' },
  { value: 'audit_investigation', label: 'Investigation', sample: 'INV-001' },
  { value: 'document_metadata', label: 'Document', sample: 'DOC-0001' },
];

const RELATIONSHIP_ORDER: Record<string, number> = {
  HAS_TRANSACTION: 1,
  HAS_CONTRACT: 2,
  HAS_COMPLIANCE_RECORD: 3,
  HAS_APPROVAL: 4,
  HAS_DOCUMENT: 5,
  SUPPORTS_FINDING: 6,
  HAS_FINDING: 7,
};

function prettyLabel(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function entityBadge(value: string) {
  return prettyLabel(value);
}

function formatValue(value: unknown): string {
  if (value == null) return '—';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map(formatValue).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function getNodeKindTone(nodeKind?: string) {
  switch (nodeKind) {
    case 'vendor':
      return '#10b981';
    case 'transaction':
      return '#3b82f6';
    case 'contract':
      return '#8b5cf6';
    case 'compliance':
      return '#f59e0b';
    case 'workflow':
      return '#06b6d4';
    case 'document':
      return '#ef4444';
    case 'finding':
      return '#ec4899';
    case 'investigation':
      return '#6366f1';
    default:
      return '#64748b';
  }
}

function GraphSummaryCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="card-sm" style={{ borderTop: '2px solid rgba(99,102,241,0.22)' }}>
      <p className="label" style={{ marginBottom: '0.2rem' }}>{label}</p>
      <strong style={{ display: 'block', fontSize: '1rem' }}>{value}</strong>
      <p className="small-copy" style={{ marginTop: '0.2rem' }}>{hint}</p>
    </div>
  );
}

function NodeChip({
  node,
  selected,
  onClick,
  compact = false,
}: {
  node: KnowledgeGraphNodeRecord;
  selected: boolean;
  onClick: () => void;
  compact?: boolean;
}) {
  const tone = getNodeKindTone(node.node_kind);
  return (
    <button
      type="button"
      onClick={onClick}
      className="card-sm"
      style={{
        textAlign: 'left',
        border: `1px solid ${selected ? tone : 'rgba(148,163,184,0.25)'}`,
        background: selected ? 'rgba(99,102,241,0.08)' : 'rgba(255,255,255,0.96)',
        boxShadow: selected ? '0 16px 34px rgba(99,102,241,0.12)' : '0 10px 24px rgba(15,23,42,0.04)',
        padding: compact ? '0.65rem 0.75rem' : '0.8rem 0.9rem',
        borderRadius: '18px',
        cursor: 'pointer',
        width: '100%',
      }}
    >
      <div className="flex-between" style={{ gap: '0.5rem', alignItems: 'flex-start' }}>
        <div style={{ minWidth: 0 }}>
          <strong style={{ display: 'block', fontSize: '0.9rem', lineHeight: 1.25 }}>{node.display_label}</strong>
          <p className="small-copy" style={{ marginTop: '0.25rem' }}>
            {entityBadge(node.entity_type)} · {node.entity_id}
          </p>
        </div>
        <span className="source-pill" style={{ background: `${tone}12`, color: tone, borderColor: `${tone}22`, flexShrink: 0 }}>
          {prettyLabel(node.node_kind)}
        </span>
      </div>
      {!compact && (
        <p className="small-copy" style={{ marginTop: '0.55rem', lineHeight: 1.45 }}>
          Relationship-ready entity node with {Object.keys(node.attributes || {}).length} attribute{Object.keys(node.attributes || {}).length === 1 ? '' : 's'}.
        </p>
      )}
    </button>
  );
}

function EdgeCard({ edge, nodes, selectedNodeId }: { edge: KnowledgeGraphEdgeRecord; nodes: KnowledgeGraphNodeRecord[]; selectedNodeId: string | null }) {
  const source = nodes.find((node) => node.node_id === edge.source_node_id);
  const target = nodes.find((node) => node.node_id === edge.target_node_id);
  const selected = selectedNodeId && (edge.source_node_id === selectedNodeId || edge.target_node_id === selectedNodeId);
  return (
    <div
      className="card-sm"
      style={{
        borderLeft: `3px solid ${selected ? '#3b82f6' : 'rgba(148,163,184,0.35)'}`,
        background: selected ? 'rgba(59,130,246,0.04)' : 'rgba(255,255,255,0.9)',
      }}
    >
      <div className="flex-between" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
        <span className="source-pill">{prettyLabel(edge.relationship_type)}</span>
        <span className="small-copy">{Math.round((edge.strength || 1) * 100)}% strength</span>
      </div>
      <p className="small-copy" style={{ marginTop: '0.45rem', lineHeight: 1.5 }}>
        <strong>{source?.display_label || edge.source_node_id}</strong> links to <strong>{target?.display_label || edge.target_node_id}</strong>
      </p>
      {edge.metadata && Object.keys(edge.metadata).length > 0 && (
        <p className="small-copy" style={{ marginTop: '0.35rem', opacity: 0.86 }}>
          {formatValue(edge.metadata)}
        </p>
      )}
    </div>
  );
}

function GraphCanvas({
  graph,
  selectedNodeId,
  onSelectNode,
}: {
  graph: KnowledgeGraphResponse;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
}) {
  const root = graph.root_node || graph.nodes[0] || null;
  const visibleNodes = useMemo(() => {
    const others = graph.nodes.filter((node) => node.node_id !== root?.node_id);
    const ordered = [...others].sort((left, right) => {
      const leftRank = RELATIONSHIP_ORDER[left.node_kind?.toUpperCase() || ''] ?? 99;
      const rightRank = RELATIONSHIP_ORDER[right.node_kind?.toUpperCase() || ''] ?? 99;
      if (leftRank !== rightRank) return leftRank - rightRank;
      return left.display_label.localeCompare(right.display_label);
    });
    return ordered.slice(0, 8);
  }, [graph.nodes, root?.node_id]);

  const centerX = 50;
  const centerY = 50;
  const radius = 32;

  return (
    <div
      style={{
        position: 'relative',
        minHeight: 480,
        borderRadius: '24px',
        background: 'radial-gradient(circle at center, rgba(99,102,241,0.08), rgba(255,255,255,0.95) 60%)',
        border: '1px solid rgba(148,163,184,0.18)',
        overflow: 'hidden',
      }}
    >
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        {root && visibleNodes.map((node, index) => {
          const angle = (Math.PI * 2 * index) / Math.max(visibleNodes.length, 1) - Math.PI / 2;
          const x = centerX + radius * Math.cos(angle);
          const y = centerY + radius * Math.sin(angle);
          return (
            <line
              key={`${root.node_id}-${node.node_id}`}
              x1={centerX}
              y1={centerY}
              x2={x}
              y2={y}
              stroke="rgba(99,102,241,0.18)"
              strokeWidth="0.7"
              strokeDasharray="1.5 1.5"
            />
          );
        })}
      </svg>

      {root && (
        <div
          style={{
            position: 'absolute',
            left: `${centerX}%`,
            top: `${centerY}%`,
            transform: 'translate(-50%, -50%)',
            zIndex: 2,
            width: 'min(320px, 42%)',
          }}
        >
          <NodeChip node={root} selected={selectedNodeId === root.node_id} onClick={() => onSelectNode(root.node_id)} />
        </div>
      )}

      {root && visibleNodes.map((node, index) => {
        const angle = (Math.PI * 2 * index) / Math.max(visibleNodes.length, 1) - Math.PI / 2;
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);
        return (
          <div
            key={node.node_id}
            style={{
              position: 'absolute',
              left: `${x}%`,
              top: `${y}%`,
              transform: 'translate(-50%, -50%)',
              zIndex: 2,
              width: 'min(240px, 28%)',
            }}
          >
            <NodeChip node={node} compact selected={selectedNodeId === node.node_id} onClick={() => onSelectNode(node.node_id)} />
          </div>
        );
      })}
    </div>
  );
}

export function KnowledgeGraphPage() {
  const [entityType, setEntityType] = useState<KnowledgeGraphEntityType>('vendor');
  const [entityId, setEntityId] = useState(ENTITY_TYPE_OPTIONS[0].sample);
  const [refresh, setRefresh] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [graph, setGraph] = useState<KnowledgeGraphResponse | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const selectedNode = useMemo(
    () => graph?.nodes.find((node) => node.node_id === selectedNodeId) || graph?.root_node || graph?.nodes[0] || null,
    [graph, selectedNodeId],
  );

  const selectedEdges = useMemo(() => {
    if (!graph || !selectedNode) return [];
    return graph.edges.filter((edge) => edge.source_node_id === selectedNode.node_id || edge.target_node_id === selectedNode.node_id);
  }, [graph, selectedNode]);

  const relatedEntityCount = Math.max((graph?.nodes.length || 0) - 1, 0);

  const loadGraph = async (nextEntityType = entityType, nextEntityId = entityId) => {
    const trimmed = nextEntityId.trim();
    if (!trimmed) {
      setError('Please enter an entity identifier before loading the graph.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await fetchKnowledgeGraph(nextEntityType, trimmed, { refresh, limit: 25 });
      setGraph(result);
      setSelectedNodeId(result.root_node?.node_id || result.nodes[0]?.node_id || null);
    } catch (err) {
      setGraph(null);
      setSelectedNodeId(null);
      setError(err instanceof Error ? err.message : 'Unable to load the knowledge graph.');
    } finally {
      setLoading(false);
    }
  };

  const summary = graph?.summary && typeof graph.summary === 'object' ? graph.summary : null;
  const relationshipBreakdown = summary && 'relationship_breakdown' in summary ? (summary.relationship_breakdown as Record<string, number>) : {};

  return (
    <div className="stack" style={{ gap: '1.25rem' }}>
      <div className="card">
        <div className="flex-between" style={{ gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <p className="eyebrow" style={{ marginBottom: '0.35rem' }}>Knowledge Graph</p>
            <h1 style={{ fontSize: '1.65rem', fontWeight: 800 }}>Entity Relationship Explorer</h1>
            <p className="body-copy" style={{ marginTop: '0.35rem', maxWidth: '72ch' }}>
              Visualize how vendors, transactions, contracts, compliance records, documents, and findings connect inside the audit workspace.
            </p>
          </div>
          <span className="source-pill" style={{ padding: '0.65rem 0.9rem' }}>
            PostgreSQL graph layer
          </span>
        </div>
      </div>

      {error && <FeedbackBanner title="Knowledge Graph Error" message={error} variant="error" />}

      <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
        <div className="card">
          <p className="label" style={{ marginBottom: '0.5rem' }}>Graph Query</p>
          <div className="grid-2" style={{ gap: '0.75rem' }}>
            <label className="stack-sm" style={{ gap: '0.35rem' }}>
              <span className="small-copy" style={{ fontWeight: 700 }}>Entity Type</span>
              <select className="input" value={entityType} onChange={(event) => {
                const nextType = event.target.value as KnowledgeGraphEntityType;
                setEntityType(nextType);
                const match = ENTITY_TYPE_OPTIONS.find((item) => item.value === nextType);
                if (match) {
                  setEntityId(match.sample);
                }
              }}>
                {ENTITY_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="stack-sm" style={{ gap: '0.35rem' }}>
              <span className="small-copy" style={{ fontWeight: 700 }}>Entity ID</span>
              <input className="input" value={entityId} onChange={(event) => setEntityId(event.target.value)} placeholder="VND-02731" />
            </label>
          </div>

          <div className="flex-between" style={{ gap: '0.75rem', marginTop: '0.85rem', flexWrap: 'wrap' }}>
            <label className="flex-row" style={{ gap: '0.45rem', alignItems: 'center' }}>
              <input type="checkbox" checked={refresh} onChange={(event) => setRefresh(event.target.checked)} />
              <span className="small-copy">Rebuild graph from source tables</span>
            </label>
            <button type="button" className="btn btn-primary" onClick={() => void loadGraph()} disabled={loading}>
              {loading ? 'Loading graph...' : 'Open Graph'}
            </button>
          </div>

          <div style={{ marginTop: '0.95rem' }}>
            <p className="label" style={{ marginBottom: '0.5rem' }}>Quick Samples</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {ENTITY_TYPE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className="source-pill"
                  onClick={() => {
                    setEntityType(option.value);
                    setEntityId(option.sample);
                    void loadGraph(option.value, option.sample);
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  {option.label} · {option.sample}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <p className="label" style={{ marginBottom: '0.5rem' }}>Graph Summary</p>
          <div className="grid-auto" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem' }}>
            <GraphSummaryCard label="Root Entity" value={graph?.root_node?.display_label || 'n/a'} hint="The selected audit entity." />
            <GraphSummaryCard label="Nodes" value={String(graph?.summary && typeof graph.summary === 'object' && 'node_count' in graph.summary ? graph.summary.node_count : graph?.nodes.length || 0)} hint="Connected relationship nodes." />
            <GraphSummaryCard label="Edges" value={String(graph?.summary && typeof graph.summary === 'object' && 'edge_count' in graph.summary ? graph.summary.edge_count : graph?.edges.length || 0)} hint="Relationship links in the graph." />
            <GraphSummaryCard label="Relationships" value={String(Object.keys(relationshipBreakdown).length || 0)} hint="Distinct relationship types." />
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ gap: '1rem', alignItems: 'start' }}>
        <div className="card">
          <div className="flex-between" style={{ gap: '0.75rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
            <div>
              <p className="label" style={{ marginBottom: '0.2rem' }}>Relationship Map</p>
              <strong style={{ fontSize: '1rem' }}>Graph neighborhood</strong>
            </div>
            {graph?.summary && typeof graph.summary === 'object' && 'generated_at' in graph.summary && (
              <span className="source-pill">Generated {new Date(String(graph.summary.generated_at)).toLocaleString()}</span>
            )}
          </div>

          {graph ? (
            <GraphCanvas graph={graph} selectedNodeId={selectedNode?.node_id || null} onSelectNode={setSelectedNodeId} />
          ) : (
            <div
              className="card-sm"
              style={{
                minHeight: 480,
                display: 'grid',
                placeItems: 'center',
                textAlign: 'center',
                background: 'linear-gradient(180deg, rgba(248,250,252,0.95), rgba(255,255,255,0.98))',
              }}
            >
              <div style={{ maxWidth: 420 }}>
                <p className="eyebrow" style={{ marginBottom: '0.35rem' }}>Ready to explore</p>
                <h3 style={{ fontSize: '1.15rem', marginBottom: '0.45rem' }}>Open a vendor, transaction, or contract to map relationships</h3>
                <p className="body-copy">
                  The graph will show linked transactions, contracts, documents, findings, and supporting evidence in one connected view.
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="stack" style={{ gap: '1rem' }}>
          <div className="card">
            <p className="label" style={{ marginBottom: '0.5rem' }}>Selected Node</p>
            {selectedNode ? (
              <div className="stack-sm">
                <NodeChip node={selectedNode} selected onClick={() => setSelectedNodeId(selectedNode.node_id)} />
                <div className="grid-2" style={{ gap: '0.65rem' }}>
                  <GraphSummaryCard label="Entity Type" value={prettyLabel(selectedNode.entity_type)} hint="The primary entity category." />
                  <GraphSummaryCard label="Node Kind" value={prettyLabel(selectedNode.node_kind)} hint="How the graph classifies the node." />
                </div>
                <div className="card-sm">
                  <p className="label" style={{ marginBottom: '0.45rem' }}>Attributes</p>
                  <div className="stack-sm">
                    {Object.entries(selectedNode.attributes || {}).slice(0, 10).map(([key, value]) => (
                      <div key={key} className="flex-between" style={{ gap: '0.75rem', alignItems: 'flex-start' }}>
                        <span className="small-copy" style={{ fontWeight: 700 }}>{prettyLabel(key)}</span>
                        <span className="small-copy" style={{ textAlign: 'right', wordBreak: 'break-word', maxWidth: '55%' }}>
                          {formatValue(value)}
                        </span>
                      </div>
                    ))}
                    {Object.keys(selectedNode.attributes || {}).length === 0 && (
                      <p className="small-copy">No additional attributes recorded.</p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <p className="small-copy">Select a node to inspect its details.</p>
            )}
          </div>

          <div className="card">
            <p className="label" style={{ marginBottom: '0.5rem' }}>Related Edges</p>
            {selectedEdges.length > 0 ? (
              <div className="stack-sm" style={{ maxHeight: 280, overflow: 'auto', paddingRight: '0.15rem' }}>
                {selectedEdges.map((edge) => (
                  <EdgeCard key={edge.edge_id} edge={edge} nodes={graph?.nodes || []} selectedNodeId={selectedNode?.node_id || null} />
                ))}
              </div>
            ) : (
              <p className="small-copy">No related edges available for the selected node.</p>
            )}
          </div>

          <div className="card">
            <p className="label" style={{ marginBottom: '0.5rem' }}>Relationship Breakdown</p>
            {Object.keys(relationshipBreakdown).length > 0 ? (
              <div className="stack-sm">
                {Object.entries(relationshipBreakdown).map(([relationship, count]) => (
                  <div key={relationship} className="flex-between" style={{ gap: '0.75rem' }}>
                    <span className="small-copy">{prettyLabel(relationship)}</span>
                    <span className="source-pill">{count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="small-copy">No relationship summary available yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

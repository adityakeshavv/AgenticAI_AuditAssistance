import { useState } from 'react';
import type { ChatMessage, CitationRecord } from '../../types/audit';
import { AuditResponsePanel } from '../AuditResponsePanel';
import { DocumentViewerModal } from '../DocumentViewerModal';
import { FeedbackBanner } from '../FeedbackBanner';

interface Props {
  msg: ChatMessage;
}

export function ChatBubble({ msg }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<CitationRecord | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const isUser = msg.role === 'user';
  const r = msg.response;

  const riskColor = !r ? undefined
    : r.risk_rating === 'HIGH' || r.risk_rating === 'CRITICAL' ? 'var(--accent-red)'
    : r.risk_rating === 'MEDIUM' ? 'var(--accent-amber)'
    : 'var(--accent-green)';
  const isErrorMessage = !r && !msg.isLoading && msg.content.trim().startsWith('⚠');

  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0.25rem 0' }}>
        <div style={{
          maxWidth: '70%',
          background: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
          color: '#fff',
          borderRadius: '18px 18px 4px 18px',
          padding: '0.75rem 1rem',
          fontSize: '0.9rem',
          lineHeight: 1.5,
          boxShadow: '0 4px 14px rgba(37,99,235,0.3)',
        }}>
          {msg.content}
        </div>
      </div>
    );
  }

  if (msg.isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.65rem', padding: '0.25rem 0' }}>
        <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))', display: 'grid', placeItems: 'center', fontSize: '0.8rem', fontWeight: 800, color: '#fff', flexShrink: 0 }}>A</div>
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '4px 18px 18px 18px', padding: '0.85rem 1.1rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{ display: 'flex', gap: '0.3rem' }}>
            {[0, 1, 2].map((i) => (
              <span key={i} style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--accent-blue)', animation: `bounce 1s ease-in-out ${i * 0.15}s infinite`, display: 'inline-block' }} />
            ))}
          </span>
          <span className="small-copy">Investigating…</span>
        </div>
        <style>{`@keyframes bounce { 0%,100%{transform:translateY(0);opacity:.6} 50%{transform:translateY(-5px);opacity:1} }`}</style>
      </div>
    );
  }

  if (isErrorMessage) {
    return (
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.65rem', padding: '0.25rem 0' }}>
        <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))', display: 'grid', placeItems: 'center', fontSize: '0.8rem', fontWeight: 800, color: '#fff', flexShrink: 0, marginTop: '0.15rem' }}>A</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <FeedbackBanner
            title="Query Error"
            message={msg.content.replace(/^⚠\s*/, '')}
            variant="error"
          />
        </div>
      </div>
    );
  }

  const summary = r
    ? (r.investigation_summary || r.transaction_summary || r.vendor_summary || r.finding?.summary || r.final_response || msg.content)
    : msg.content;

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.65rem', padding: '0.25rem 0' }}>
      {/* Avatar */}
      <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))', display: 'grid', placeItems: 'center', fontSize: '0.8rem', fontWeight: 800, color: '#fff', flexShrink: 0, marginTop: '0.15rem' }}>A</div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Bubble */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '4px 18px 18px 18px', padding: '0.9rem 1.1rem', marginBottom: '0.5rem' }}>
          {/* Follow-up tag */}
          {r?.is_followup && (
            <div style={{ marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.25)', borderRadius: '999px', color: '#c4b5fd' }}>
                ↩ Follow-up resolved
              </span>
            </div>
          )}

          {/* Finding title */}
          {r?.finding?.title && r.finding.title !== 'Unsupported Query' && (
            <p style={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>{r.finding.title}</p>
          )}

          {/* Summary text */}
          <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)', lineHeight: 1.6, margin: 0 }}>
            {String(summary).slice(0, expanded ? undefined : 500)}
            {!expanded && String(summary).length > 500 && (
              <button onClick={() => setExpanded(true)} style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer', fontSize: '0.85rem', padding: '0 0.25rem' }}>…read more</button>
            )}
          </p>

          {/* Meta row */}
          {r && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.65rem', paddingTop: '0.65rem', borderTop: '1px solid var(--border)' }}>
              {r.risk_rating && (
                <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.55rem', borderRadius: '999px', background: `${riskColor}18`, color: riskColor, border: `1px solid ${riskColor}40` }}>
                  {r.risk_rating} Risk · {r.risk_score}
                </span>
              )}
              {r.citations.length > 0 && <span className="source-pill">{r.citations.length} citation{r.citations.length !== 1 ? 's' : ''}</span>}
              {r.agents_used.length > 0 && <span className="source-pill">{r.agents_used.length} agent{r.agents_used.length !== 1 ? 's' : ''}</span>}
              {r.structured_evidence.length > 0 && <span className="source-pill">{r.structured_evidence.length} records</span>}
              <span style={{ marginLeft: 'auto', fontSize: '0.72rem', color: 'var(--text-muted)' }}>{new Date(msg.timestamp).toLocaleTimeString()}</span>
            </div>
          )}
        </div>

        {/* Expandable detail panel */}
        {r && (
          <div>
            <button
              onClick={() => setExpanded((v) => !v)}
              style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '0.35rem 0.75rem', color: 'var(--text-muted)', fontSize: '0.8rem', cursor: 'pointer', marginBottom: expanded ? '0.75rem' : 0, transition: 'all 0.15s' }}
            >
              {expanded ? '▲ Hide Details' : '▼ Show Evidence & Traceability'}
            </button>
            {expanded && (
              <AuditResponsePanel
                response={r}
                onCitationSelect={(c) => { setSelectedCitation(c); setModalOpen(true); }}
              />
            )}
          </div>
        )}
      </div>

      <DocumentViewerModal open={modalOpen} citation={selectedCitation} onClose={() => setModalOpen(false)} />
    </div>
  );
}

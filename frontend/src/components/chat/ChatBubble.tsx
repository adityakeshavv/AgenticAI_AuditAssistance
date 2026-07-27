import { useEffect, useMemo, useState } from 'react';

import type { ChatMessage, CitationRecord } from '../../types/audit';
import { AuditResponsePanel } from '../AuditResponsePanel';
import { DocumentViewerModal } from '../DocumentViewerModal';
import { FeedbackBanner } from '../FeedbackBanner';

interface Props {
  msg: ChatMessage;
}

function useTypingText(text: string, enabled: boolean): string {
  const [displayText, setDisplayText] = useState('');

  useEffect(() => {
    if (!enabled) {
      setDisplayText(text);
      return;
    }

    let index = 0;
    setDisplayText('');
    const step = Math.max(1, Math.ceil(text.length / 24));
    const timer = window.setInterval(() => {
      index += step;
      setDisplayText(text.slice(0, index));
      if (index >= text.length) {
        window.clearInterval(timer);
      }
    }, 18);
    return () => window.clearInterval(timer);
  }, [enabled, text]);

  return displayText;
}

export function ChatBubble({ msg }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<CitationRecord | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const isUser = msg.role === 'user';
  const response = msg.response;
  const conversationMode = response?.conversation_mode || 'audit';
  const isConversationReply = Boolean(response) && conversationMode !== 'audit';
  const isAuditReply = Boolean(response) && !isConversationReply;

  const citationCount = response?.citations?.length ?? 0;
  const agentCount = response?.agents_used?.length ?? 0;
  const evidenceCount = response?.structured_evidence?.length ?? 0;

  const riskColor = !response
    ? undefined
    : response.risk_rating === 'HIGH' || response.risk_rating === 'CRITICAL'
      ? 'var(--accent-red)'
      : response.risk_rating === 'MEDIUM'
        ? 'var(--accent-amber)'
        : 'var(--accent-green)';

  const isErrorMessage = !response && !msg.isLoading && msg.content.trim().startsWith('⚠');
  const summaryText = useMemo(() => {
    if (!response) return msg.content;
    if (isConversationReply) {
      return response.assistant_message || response.final_response || msg.content;
    }
    return response.investigation_summary || response.transaction_summary || response.vendor_summary || response.finding?.summary || response.final_response || msg.content;
  }, [isConversationReply, msg.content, response]);
  const animatedSummary = useTypingText(String(summaryText), Boolean(response && !msg.isLoading));

  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0.25rem 0' }}>
        <div
          style={{
            maxWidth: '72%',
            background: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
            color: '#fff',
            borderRadius: '18px 18px 4px 18px',
            padding: '0.8rem 1rem',
            fontSize: '0.92rem',
            lineHeight: 1.6,
            boxShadow: '0 6px 18px rgba(37,99,235,0.24)',
            whiteSpace: 'pre-wrap',
          }}
        >
          {msg.content}
        </div>
      </div>
    );
  }

  if (msg.isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.65rem', padding: '0.25rem 0' }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))',
            display: 'grid',
            placeItems: 'center',
            fontSize: '0.8rem',
            fontWeight: 800,
            color: '#fff',
            flexShrink: 0,
          }}
        >
          A
        </div>
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: '4px 18px 18px 18px',
            padding: '0.85rem 1.1rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            boxShadow: '0 10px 28px rgba(15,23,42,0.05)',
          }}
        >
          <span style={{ display: 'flex', gap: '0.3rem' }}>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: '50%',
                  background: 'var(--accent-blue)',
                  animation: `bounce 1s ease-in-out ${i * 0.15}s infinite`,
                  display: 'inline-block',
                }}
              />
            ))}
          </span>
          <span className="small-copy">Thinking...</span>
        </div>
        <style>{`@keyframes bounce { 0%,100%{transform:translateY(0);opacity:.6} 50%{transform:translateY(-5px);opacity:1} }`}</style>
      </div>
    );
  }

  if (isErrorMessage) {
    return (
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.65rem', padding: '0.25rem 0' }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))',
            display: 'grid',
            placeItems: 'center',
            fontSize: '0.8rem',
            fontWeight: 800,
            color: '#fff',
            flexShrink: 0,
            marginTop: '0.15rem',
          }}
        >
          A
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <FeedbackBanner title="Query Error" message={msg.content.replace(/^⚠\s*/, '')} variant="error" />
        </div>
      </div>
    );
  }

  if (isConversationReply) {
    return (
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.65rem', padding: '0.25rem 0' }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))',
            display: 'grid',
            placeItems: 'center',
            fontSize: '0.8rem',
            fontWeight: 800,
            color: '#fff',
            flexShrink: 0,
            marginTop: '0.15rem',
          }}
        >
          A
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: '4px 18px 18px 18px',
              padding: '0.95rem 1.1rem',
              marginBottom: '0.35rem',
              boxShadow: '0 10px 28px rgba(15,23,42,0.05)',
            }}
          >
            {response?.is_followup && (
              <div style={{ marginBottom: '0.5rem' }}>
                <span
                  style={{
                    fontSize: '0.72rem',
                    padding: '0.15rem 0.5rem',
                    background: 'rgba(99,102,241,0.10)',
                    border: '1px solid rgba(99,102,241,0.18)',
                    borderRadius: '999px',
                    color: '#6366f1',
                  }}
                >
                  Follow-up
                </span>
              </div>
            )}
            <p style={{ fontSize: '0.94rem', color: 'var(--text-primary)', lineHeight: 1.7, margin: 0, whiteSpace: 'pre-wrap' }}>
              {animatedSummary}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const summary = animatedSummary;

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.65rem', padding: '0.25rem 0' }}>
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))',
          display: 'grid',
          placeItems: 'center',
          fontSize: '0.8rem',
          fontWeight: 800,
          color: '#fff',
          flexShrink: 0,
          marginTop: '0.15rem',
        }}
      >
        A
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: '4px 18px 18px 18px',
            padding: '0.95rem 1.1rem',
            marginBottom: '0.5rem',
            boxShadow: '0 10px 28px rgba(15,23,42,0.05)',
          }}
        >
          {response?.is_followup && (
            <div style={{ marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.25)', borderRadius: '999px', color: '#8b5cf6' }}>
                Follow-up resolved
              </span>
            </div>
          )}

          {response?.finding?.title && response.finding.title !== 'Unsupported Query' && (
            <p style={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>
              {response.finding.title}
            </p>
          )}

          <p style={{ fontSize: '0.92rem', color: 'var(--text-primary)', lineHeight: 1.7, margin: 0, whiteSpace: 'pre-wrap' }}>
            {summary}
            {!expanded && String(summary).length > 500 && (
              <button
                onClick={() => setExpanded(true)}
                style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer', fontSize: '0.85rem', padding: '0 0.25rem' }}
              >
                ...read more
              </button>
            )}
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border)' }}>
            {response?.risk_rating && response.conversation_mode === 'audit' && (
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  padding: '0.2rem 0.55rem',
                  borderRadius: '999px',
                  background: `${riskColor}18`,
                  color: riskColor,
                  border: `1px solid ${riskColor}40`,
                }}
              >
                {response.risk_rating} Risk · {response.risk_score}
              </span>
            )}
            {citationCount > 0 && <span className="source-pill">{citationCount} citation{citationCount !== 1 ? 's' : ''}</span>}
            {agentCount > 0 && <span className="source-pill">{agentCount} agent{agentCount !== 1 ? 's' : ''}</span>}
            {evidenceCount > 0 && <span className="source-pill">{evidenceCount} records</span>}
            <span style={{ marginLeft: 'auto', fontSize: '0.72rem', color: 'var(--text-muted)' }}>{new Date(msg.timestamp).toLocaleTimeString()}</span>
          </div>
        </div>

        {response && response.conversation_mode === 'audit' && (
          <div>
            <button
              onClick={() => setExpanded((v) => !v)}
              style={{
                background: 'none',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.35rem 0.75rem',
                color: 'var(--text-muted)',
                fontSize: '0.8rem',
                cursor: 'pointer',
                marginBottom: expanded ? '0.75rem' : 0,
                transition: 'all 0.15s',
              }}
            >
              {expanded ? 'Hide details' : 'Show evidence and traceability'}
            </button>
            {expanded && (
              <AuditResponsePanel
                response={response}
                onCitationSelect={(citation) => {
                  setSelectedCitation(citation);
                  setModalOpen(true);
                }}
              />
            )}
          </div>
        )}
      </div>

      <DocumentViewerModal open={modalOpen} citation={selectedCitation} onClose={() => setModalOpen(false)} />
    </div>
  );
}

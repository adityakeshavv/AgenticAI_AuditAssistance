import { useEffect, useRef, useState } from 'react';

import type { ChatMessage, ChatResponse, InvestigationState, SuggestedAction } from '../../types/audit';
import { sendChatMessage } from '../../services/auditApi';
import { ChatBubble } from './ChatBubble';
import { ChatInput } from './ChatInput';
import { SuggestedActions } from './SuggestedActions';
import { InvestigationSidebar } from './InvestigationSidebar';

const STARTER_QUERIES = [
  'Investigate vendor VND-02731 for compliance issues',
  'Show all flagged transactions above $50,000',
  'Show vendors with expired compliance certifications',
  'Which approvals exceeded the approver authority limit?',
  'Show expense claims with missing receipts',
];

const EMPTY_INVESTIGATION: InvestigationState = {
  entity_ids: [], transaction_ids: [], topics: [],
  transaction_count: 0, document_count: 0, finding_count: 0,
  key_findings: [], recommendations: [], status: 'idle',
};

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [suggestedActions, setSuggestedActions] = useState<SuggestedAction[]>([]);
  const [investigationState, setInvestigationState] = useState<InvestigationState>(EMPTY_INVESTIGATION);
  const [turnCount, setTurnCount] = useState(0);
  const [showSidebar, setShowSidebar] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;
    setInput('');

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(), role: 'user', content: trimmed,
      timestamp: new Date().toISOString(),
    };
    const loadingMsg: ChatMessage = {
      id: crypto.randomUUID(), role: 'assistant', content: '',
      timestamp: new Date().toISOString(), isLoading: true,
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setIsLoading(true);
    setSuggestedActions([]);

    try {
      const response: ChatResponse = await sendChatMessage(trimmed, sessionId);

      // Update session and state
      setSessionId(response.session_id);
      setTurnCount(response.turn_count);
      if (response.investigation_state) {
        setInvestigationState(response.investigation_state);
      }
      if (response.suggested_actions?.length) {
        setSuggestedActions(response.suggested_actions);
      }

      const summary = response.investigation_summary
        || response.transaction_summary
        || response.vendor_summary
        || response.finding?.summary
        || response.final_response
        || 'Investigation complete.';

      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(), role: 'assistant',
        content: String(summary),
        timestamp: new Date().toISOString(),
        response,
      };

      setMessages((prev) => [...prev.slice(0, -1), assistantMsg]);
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(), role: 'assistant',
        content: `⚠ ${err instanceof Error ? err.message : 'An error occurred. Please try again.'}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev.slice(0, -1), errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActionSelect = (action: SuggestedAction) => {
    sendMessage(action.description || action.label);
  };

  const handleClear = () => {
    setMessages([]);
    setSessionId(null);
    setSuggestedActions([]);
    setInvestigationState(EMPTY_INVESTIGATION);
    setTurnCount(0);
  };

  const isEmpty = messages.length === 0;

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 60px)', overflow: 'hidden' }}>
      {/* ── Main chat column ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        {/* Chat header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0.75rem 1.25rem',
          borderBottom: '1px solid var(--border)',
          background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(8px)',
          gap: '1rem', flexShrink: 0,
        }}>
          <div>
            <p className="eyebrow" style={{ margin: 0 }}>Audit Copilot</p>
            <h2 style={{ margin: '0.1rem 0 0', fontSize: '1rem', fontWeight: 700 }}>
              {sessionId ? `Session · Turn ${turnCount}` : 'New Investigation'}
            </h2>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            {sessionId && (
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                {sessionId.slice(0, 8)}
              </span>
            )}
            <button className="btn btn-ghost" onClick={() => setShowSidebar((v) => !v)} style={{ fontSize: '0.8rem' }}>
              {showSidebar ? '⇥ Hide Panel' : '⇤ Show Panel'}
            </button>
            {messages.length > 0 && (
              <button className="btn btn-secondary" onClick={handleClear} style={{ fontSize: '0.8rem' }}>
                New Session
              </button>
            )}
          </div>
        </div>

        {/* Messages area */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem 1.25rem 0' }}>
          {isEmpty ? (
            /* Welcome screen */
            <div style={{ maxWidth: 580, margin: '3rem auto', textAlign: 'center' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem', opacity: 0.5 }}>🔍</div>
              <h2 style={{ fontSize: '1.5rem', fontWeight: 800, marginBottom: '0.5rem' }}>Audit Copilot</h2>
              <p className="body-copy" style={{ marginBottom: '2rem', color: 'var(--text-secondary)' }}>
                Ask anything about transactions, vendors, evidence, or compliance. I'll remember the context as we investigate together.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', textAlign: 'left' }}>
                {STARTER_QUERIES.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    style={{
                      padding: '0.7rem 1rem',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-md)',
                      color: 'var(--text-primary)',
                      fontSize: '0.88rem',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s',
                      display: 'flex', alignItems: 'center', gap: '0.65rem',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--border-hi)'; e.currentTarget.style.background = 'var(--bg-hover)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--bg-card)'; }}
                  >
                    <span style={{ color: 'var(--accent-blue)', flexShrink: 0 }}>→</span>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ maxWidth: 820, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '0.75rem', paddingBottom: '1rem' }}>
              {messages.map((msg) => <ChatBubble key={msg.id} msg={msg} />)}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Suggested actions + input */}
        <div style={{
          padding: '0.75rem 1.25rem 1rem',
          borderTop: '1px solid var(--border)',
          background: 'rgba(255,255,255,0.95)',
          backdropFilter: 'blur(8px)',
          flexShrink: 0,
        }}>
          {suggestedActions.length > 0 && (
            <div style={{ maxWidth: 820, margin: '0 auto 0.65rem' }}>
              <SuggestedActions actions={suggestedActions} onSelect={handleActionSelect} disabled={isLoading} />
            </div>
          )}
          <div style={{ maxWidth: 820, margin: '0 auto' }}>
            <ChatInput
              value={input}
              onChange={setInput}
              onSubmit={() => sendMessage(input)}
              disabled={isLoading}
            />
          </div>
        </div>
      </div>

      {/* ── Investigation Sidebar ── */}
      {showSidebar && (
        <InvestigationSidebar state={investigationState} turnCount={turnCount} />
      )}
    </div>
  );
}

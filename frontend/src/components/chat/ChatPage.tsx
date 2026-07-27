import { useEffect, useRef, useState, type ChangeEvent } from 'react';

import type { ChatMessage, ChatResponse, InvestigationState, SuggestedAction } from '../../types/audit';
import type { DocumentMetadataRecord } from '../../types/databaseConnections';
import { sendChatMessage } from '../../services/auditApi';
import { uploadDocumentSource } from '../../services/databaseConnectionsApi';
import { getSelectedWorkspaceId } from '../../services/workspacesApi';
import { ChatBubble } from './ChatBubble';
import { ChatInput } from './ChatInput';
import { InvestigationSidebar } from './InvestigationSidebar';
import { SuggestedActions } from './SuggestedActions';

const STARTER_QUERIES = [
  'Investigate vendor VND-02731 for compliance issues',
  'Show all flagged transactions above $50,000',
  'Show vendors with expired compliance certifications',
  'Which approvals exceeded the approver authority limit?',
  'Show expense claims with missing receipts',
];

const EMPTY_INVESTIGATION: InvestigationState = {
  entity_ids: [],
  transaction_ids: [],
  topics: [],
  transaction_count: 0,
  document_count: 0,
  finding_count: 0,
  key_findings: [],
  recommendations: [],
  status: 'idle',
};

function toDocumentRecord(value: unknown): DocumentMetadataRecord | null {
  if (!value || typeof value !== 'object') return null;
  const document = value as Partial<DocumentMetadataRecord>;
  if (!document.document_id || !document.file_name) return null;
  return {
    document_id: document.document_id,
    document_type: document.document_type || 'document',
    document_category: document.document_category || 'uploaded',
    related_vendor_id: document.related_vendor_id ?? null,
    related_employee_id: document.related_employee_id ?? null,
    related_transaction_id: document.related_transaction_id ?? null,
    related_contract_id: document.related_contract_id ?? null,
    related_investigation_id: document.related_investigation_id ?? null,
    creation_date: document.creation_date || new Date().toISOString().slice(0, 10),
    file_name: document.file_name,
    file_path: document.file_path || '',
    source_uri: document.source_uri || '',
    source_metadata_file: document.source_metadata_file || '',
    created_at: document.created_at ?? null,
    updated_at: document.updated_at ?? null,
  };
}

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [suggestedActions, setSuggestedActions] = useState<SuggestedAction[]>([]);
  const [investigationState, setInvestigationState] = useState<InvestigationState>(EMPTY_INVESTIGATION);
  const [turnCount, setTurnCount] = useState(0);
  const [showSidebar, setShowSidebar] = useState(true);
  const [showTools, setShowTools] = useState(false);
  const [attachedDocuments, setAttachedDocuments] = useState<DocumentMetadataRecord[]>([]);

  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeWorkspaceId = getSelectedWorkspaceId();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const appendAssistantResponse = (response: ChatResponse) => {
    setSessionId(response.session_id);
    setTurnCount(response.turn_count);

    if (response.investigation_state) {
      setInvestigationState(response.investigation_state);
    }

    if (response.suggested_actions?.length) {
      setSuggestedActions(response.suggested_actions);
    } else {
      setSuggestedActions([]);
    }

    const summary =
      response.investigation_summary ||
      response.transaction_summary ||
      response.vendor_summary ||
      response.finding?.summary ||
      response.final_response ||
      'Investigation complete.';

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: String(summary),
      timestamp: new Date().toISOString(),
      response,
    };

    setMessages((prev) => [...prev.slice(0, -1), assistantMsg]);
  };

  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    setInput('');
    setUploadError(null);

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    };
    const loadingMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isLoading: true,
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setIsLoading(true);
    setSuggestedActions([]);

    try {
      const response: ChatResponse = await sendChatMessage(
        trimmed,
        sessionId,
        attachedDocuments.map((document) => document.document_id),
      );
      appendAssistantResponse(response);
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'An error occurred. Please try again.'}`,
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
    setShowTools(false);
    setUploadError(null);
  };

  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (!files.length) return;

    setIsUploading(true);
    setUploadError(null);

    try {
      const uploaded: DocumentMetadataRecord[] = [];
      for (const file of files) {
        const result = await uploadDocumentSource({ file });
        const record = toDocumentRecord(result.document);
        if (record) {
          uploaded.push(record);
        }
      }
      if (uploaded.length > 0) {
        setAttachedDocuments((prev) => [...prev, ...uploaded]);
        setShowTools(true);
      }
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Failed to upload document.');
    } finally {
      setIsUploading(false);
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div style={{ display: 'flex', gap: '1rem', height: 'calc(100vh - 60px)', overflow: 'hidden', minWidth: 0 }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            padding: '0.9rem 1.2rem',
            borderBottom: '1px solid var(--border)',
            background: 'rgba(255,255,255,0.94)',
            backdropFilter: 'blur(10px)',
            flexShrink: 0,
          }}
        >
          <div>
            <p className="eyebrow" style={{ margin: 0 }}>
              Audit Copilot
            </p>
            <h2 style={{ margin: '0.12rem 0 0', fontSize: '1rem', fontWeight: 700 }}>
              {sessionId ? `Session · Turn ${turnCount}` : 'New Investigation'}
            </h2>
            <p className="small-copy" style={{ marginTop: '0.2rem' }}>
              {activeWorkspaceId ? `Workspace scoped · ${activeWorkspaceId}` : 'No workspace selected'}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            {sessionId && (
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                {sessionId.slice(0, 8)}
              </span>
            )}
            <button type="button" className="btn btn-ghost" onClick={() => setShowSidebar((v) => !v)} style={{ fontSize: '0.8rem' }}>
              {showSidebar ? 'Hide panel' : 'Show panel'}
            </button>
            {messages.length > 0 && (
              <button type="button" className="btn btn-secondary" onClick={handleClear} style={{ fontSize: '0.8rem' }}>
                New session
              </button>
            )}
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '1.1rem 1.1rem 0' }}>
          {isEmpty ? (
            <div style={{ maxWidth: 620, margin: '2.5rem auto', textAlign: 'center' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem', opacity: 0.5 }}>Search</div>
              <h2 style={{ fontSize: '1.45rem', fontWeight: 800, marginBottom: '0.5rem' }}>Audit Copilot</h2>
              <p className="body-copy" style={{ marginBottom: '1.5rem', color: 'var(--text-secondary)' }}>
                Ask about transactions, vendors, evidence, or compliance and I'll keep the investigation context as we go.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem', textAlign: 'left' }}>
                {STARTER_QUERIES.map((query) => (
                  <button
                    key={query}
                    type="button"
                    onClick={() => sendMessage(query)}
                    style={{
                      padding: '0.72rem 0.95rem',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-md)',
                      color: 'var(--text-primary)',
                      fontSize: '0.88rem',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.65rem',
                    }}
                  >
                    <span style={{ color: 'var(--accent-blue)', flexShrink: 0 }}>-&gt;</span>
                    {query}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ maxWidth: 860, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '0.75rem', paddingBottom: '1rem' }}>
              {messages.map((message) => (
                <ChatBubble key={message.id} msg={message} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div
          style={{
            padding: '0.6rem 1.1rem 0.95rem',
            borderTop: '1px solid var(--border)',
            background: 'rgba(255,255,255,0.96)',
            backdropFilter: 'blur(10px)',
            flexShrink: 0,
          }}
        >
          <div
            style={{
              maxWidth: 860,
              margin: '0 auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.55rem',
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.txt,.eml,.md,.csv,.xlsx,.xls"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-secondary" onClick={handleAttachClick} disabled={isUploading || isLoading} style={{ fontSize: '0.8rem' }}>
                {isUploading ? 'Uploading...' : 'Attach docs'}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowTools((value) => !value)}
                style={{ fontSize: '0.8rem' }}
                disabled={isLoading}
              >
                {showTools ? 'Hide tools' : 'Show tools'}
              </button>
              {attachedDocuments.length > 0 && (
                <span className="source-pill" style={{ fontSize: '0.72rem' }}>
                  {attachedDocuments.length} attached
                </span>
              )}
              {suggestedActions.length > 0 && (
                <span className="source-pill" style={{ fontSize: '0.72rem' }}>
                  {suggestedActions.length} next steps
                </span>
              )}
            </div>

            {showTools && (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 1fr)',
                  gap: '0.75rem',
                  padding: '0.85rem',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border)',
                  borderRadius: '18px',
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <p className="label" style={{ marginBottom: '0.5rem' }}>
                    Attached Documents
                  </p>
                  {attachedDocuments.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                      {attachedDocuments.map((document) => (
                        <div
                          key={document.document_id}
                          style={{
                            padding: '0.55rem 0.7rem',
                            border: '1px solid var(--border)',
                            borderRadius: '12px',
                            background: 'rgba(255,255,255,0.74)',
                          }}
                        >
                          <div style={{ fontWeight: 700, fontSize: '0.86rem', color: 'var(--text-primary)' }}>{document.file_name}</div>
                          <div className="small-copy" style={{ marginTop: '0.2rem' }}>
                            {document.document_category} · {document.document_type}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="small-copy" style={{ margin: 0 }}>
                      No attached documents yet.
                    </p>
                  )}
                  {uploadError && (
                    <div
                      style={{
                        marginTop: '0.65rem',
                        padding: '0.55rem 0.7rem',
                        borderRadius: '12px',
                        border: '1px solid rgba(239,68,68,0.25)',
                        background: 'rgba(239,68,68,0.08)',
                        color: 'var(--accent-red)',
                        fontSize: '0.82rem',
                      }}
                    >
                      {uploadError}
                    </div>
                  )}
                </div>

                <div style={{ minWidth: 0 }}>
                  <p className="label" style={{ marginBottom: '0.5rem' }}>
                    Suggested Next Steps
                  </p>
                  {suggestedActions.length > 0 ? (
                    <SuggestedActions actions={suggestedActions} onSelect={handleActionSelect} disabled={isLoading} />
                  ) : (
                    <p className="small-copy" style={{ margin: 0 }}>
                      Suggestions will appear after the first response.
                    </p>
                  )}
                </div>
              </div>
            )}

            <ChatInput value={input} onChange={setInput} onSubmit={() => sendMessage(input)} disabled={isLoading} />
          </div>
        </div>
      </div>

      {showSidebar && (
        <div style={{ width: '320px', flexShrink: 0, display: 'flex', minWidth: 0 }}>
          <InvestigationSidebar state={investigationState} turnCount={turnCount} onCollapse={() => setShowSidebar(false)} />
        </div>
      )}
    </div>
  );
}

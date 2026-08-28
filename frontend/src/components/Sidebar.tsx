import { relativeTime } from "../format";
import type { ConversationSummary } from "../types";

export function Brand() {
  return (
    <div className="brand">
      <img src="/graph.svg" alt="" />
      <div>
        <h1>
          Talent<span>Graph</span>
        </h1>
        <p>Conversational KG</p>
      </div>
    </div>
  );
}

interface Props {
  threads: ConversationSummary[];
  activeId: string;
  threadsError: boolean;
  disabled: boolean;
  open: boolean;
  cvCount: number;
  /** Signed-in account, or null when auth is not configured (local dev). */
  username: string | null;
  onNew: () => void;
  onOpenLibrary: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onSignOut: () => void;
}

export function Sidebar({
  threads,
  activeId,
  threadsError,
  disabled,
  open,
  cvCount,
  username,
  onNew,
  onOpenLibrary,
  onSelect,
  onDelete,
  onSignOut,
}: Props) {
  return (
    <aside className={open ? "sidebar open" : "sidebar"}>
      <Brand />

      <div className="sidebar-actions">
        <button className="new-conversation" onClick={onNew}>
          New chat
        </button>
        <button className="cv-library-open" onClick={onOpenLibrary}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M4 2h5l3 3v9H4V2z"
              stroke="currentColor"
              strokeWidth="1.3"
              strokeLinejoin="round"
            />
            <path d="M9 2v3h3" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
          </svg>
          CV library
          <span className="cv-library-count">{cvCount}</span>
        </button>
      </div>

      <div className="threads-section">
        <h2>Threads</h2>
        {threadsError ? (
          <p className="threads-note">Could not load chat history.</p>
        ) : threads.length === 0 ? (
          <p className="threads-note">No conversations yet.</p>
        ) : (
          <div className="threads">
            {threads.map((t) => (
              <div
                key={t.conversation_id}
                className={
                  t.conversation_id === activeId ? "thread-item active" : "thread-item"
                }
              >
                <button
                  className="thread-select"
                  disabled={disabled}
                  onClick={() => onSelect(t.conversation_id)}
                >
                  <span className="thread-title">{t.title}</span>
                  <span className="thread-time">{relativeTime(t.updated_at)}</span>
                </button>
                <button
                  className="thread-delete"
                  aria-label={`Delete "${t.title}"`}
                  disabled={disabled}
                  onClick={() => onDelete(t.conversation_id)}
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                    <path
                      d="M2.5 2.5l7 7M9.5 2.5l-7 7"
                      stroke="currentColor"
                      strokeWidth="1.4"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {username && (
        <div className="sidebar-account">
          <span className="account-name" title={username}>
            {username}
          </span>
          <button className="sign-out" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      )}
    </aside>
  );
}

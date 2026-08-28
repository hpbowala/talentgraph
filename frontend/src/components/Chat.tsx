import { useCallback, useEffect, useRef, useState } from "react";
import {
  deleteConversation,
  getConversation,
  listConversations,
  listCVs,
  sendChat,
} from "../api";
import type {
  ConversationSummary,
  ConversationTurn,
  CVLibrary,
  Message,
} from "../types";
import { Brand, Sidebar } from "./Sidebar";
import { MessageView } from "./MessageView";
import { Composer } from "./Composer";
import { CVLibraryPanel } from "./CVLibrary";
import { useSession } from "../session-context";
import { trackSpotlight } from "../spotlight";

const EXAMPLES = [
  "Who has Python experience?",
  "Who has both Python and AWS?",
  "How is Alice connected to NLP?",
  "Who would suit a Python and AWS AI project?",
  "Build a three-person team for Python, AWS and React",
  "Why Alice over David for an AI project?",
  "Which people have overlapping skills?",
];

const ACTIVE_THREAD_KEY = "tg-conversation";

function newConversationId(): string {
  return `web-${crypto.randomUUID()}`;
}

function loadConversationId(): string {
  try {
    const existing = localStorage.getItem(ACTIVE_THREAD_KEY);
    if (existing) return existing;
  } catch {
    /* storage unavailable */
  }
  return newConversationId();
}

function storeConversationId(id: string) {
  try {
    localStorage.setItem(ACTIVE_THREAD_KEY, id);
  } catch {
    /* ignore */
  }
}

function turnsToMessages(turns: ConversationTurn[]): Message[] {
  return turns.flatMap((t) => [
    { role: "user" as const, content: t.user },
    {
      role: "assistant" as const,
      content: t.answer,
      intent: t.intent,
      evidence: t.evidence,
    },
  ]);
}

export function Chat() {
  const { username, signOut } = useSession();
  const [conversationId, setConversationId] = useState(loadConversationId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [threads, setThreads] = useState<ConversationSummary[]>([]);
  const [threadsError, setThreadsError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [library, setLibrary] = useState<CVLibrary | null>(null);
  const [libraryError, setLibraryError] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  const refreshThreads = useCallback(async () => {
    try {
      setThreads(await listConversations());
      setThreadsError(false);
    } catch {
      setThreadsError(true);
    }
  }, []);

  const refreshLibrary = useCallback(async () => {
    try {
      setLibrary(await listCVs());
      setLibraryError(false);
    } catch {
      setLibraryError(true);
    }
  }, []);

  // On mount: load the thread list, the CV library and the last-active
  // transcript. RequireAuth guarantees a session before any of this runs.
  useEffect(() => {
    void refreshThreads();
    void refreshLibrary();
    let cancelled = false;
    getConversation(loadConversationId())
      .then((detail) => {
        if (!cancelled && detail) setMessages(turnsToMessages(detail.turns));
      })
      .catch(() => {
        /* fresh thread not on the server yet, or service unreachable */
      });
    return () => {
      cancelled = true;
    };
  }, [refreshThreads, refreshLibrary]);

  useEffect(() => {
    storeConversationId(conversationId);
  }, [conversationId]);

  const ask = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || loading) return;
      setMenuOpen(false);
      setMessages((prev) => [...prev, { role: "user", content: question }]);
      setLoading(true);
      try {
        const res = await sendChat(question, conversationId);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: res.answer,
            intent: res.intent,
            evidence: res.evidence,
          },
        ]);
        void refreshThreads();
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            role: "error",
            content:
              err instanceof Error
                ? err.message
                : "Could not reach the TalentGraph service.",
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [conversationId, loading, refreshThreads],
  );

  const openLibrary = useCallback(() => {
    setMenuOpen(false);
    setLibraryOpen(true);
    void refreshLibrary();
  }, [refreshLibrary]);

  const newChat = useCallback(() => {
    setConversationId(newConversationId());
    setMessages([]);
    setMenuOpen(false);
  }, []);

  const selectThread = useCallback(
    async (id: string) => {
      if (loading) return;
      setMenuOpen(false);
      if (id === conversationId) return;
      try {
        const detail = await getConversation(id);
        if (!detail) {
          // Deleted elsewhere — drop it from the list.
          setThreads((prev) => prev.filter((t) => t.conversation_id !== id));
          return;
        }
        setConversationId(id);
        setMessages(turnsToMessages(detail.turns));
      } catch {
        setThreadsError(true);
      }
    },
    [conversationId, loading],
  );

  const endSession = useCallback(() => {
    setMessages([]);
    setThreads([]);
    setLibrary(null);
    setMenuOpen(false);
    signOut();
  }, [signOut]);

  const deleteThread = useCallback(
    async (id: string) => {
      try {
        await deleteConversation(id);
        setThreads((prev) => prev.filter((t) => t.conversation_id !== id));
        if (id === conversationId) {
          setConversationId(newConversationId());
          setMessages([]);
        }
      } catch {
        setThreadsError(true);
      }
    },
    [conversationId],
  );

  return (
    <div className="app">
      <div className="ambient" aria-hidden="true">
        <div className="blob blob-a" />
        <div className="blob blob-b" />
        <div className="blob blob-c" />
        <div className="blob blob-d" />
      </div>
      <header className="mobile-bar">
        <Brand />
        <button
          className="menu-toggle"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          )}
        </button>
      </header>
      <Sidebar
        threads={threads}
        activeId={conversationId}
        threadsError={threadsError}
        disabled={loading}
        open={menuOpen}
        cvCount={library?.cvs.length ?? 0}
        username={username}
        onNew={newChat}
        onOpenLibrary={openLibrary}
        onSelect={selectThread}
        onDelete={deleteThread}
        onSignOut={endSession}
      />
      <main className="main">
        <div className="chat-scroll" ref={scrollRef}>
          <div className="chat-inner">
            {messages.length === 0 && !loading ? (
              <div className="empty">
                <div className="overline">Workforce Intelligence</div>
                <h2>Ask the graph who can build what.</h2>
                <div className="suggestions">
                  {EXAMPLES.map((q) => (
                    <button
                      key={q}
                      className="chip spot"
                      onClick={() => ask(q)}
                      onMouseMove={trackSpotlight}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m, i) => <MessageView key={i} message={m} />)
            )}
            {loading && (
              <div className="thinking">
                <span className="nodes">
                  <span />
                  <span />
                  <span />
                </span>
                traversing the graph…
              </div>
            )}
          </div>
        </div>
        <Composer disabled={loading} onSubmit={ask} />
      </main>
      {libraryOpen && (
        <CVLibraryPanel
          library={library}
          loadError={libraryError}
          onClose={() => setLibraryOpen(false)}
          onChange={(next) => {
            setLibrary(next);
            setLibraryError(false);
          }}
        />
      )}
    </div>
  );
}

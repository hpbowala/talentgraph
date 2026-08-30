import { getAccessToken, notifyUnauthorized, signOut } from "./auth";
import type {
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  CVLibrary,
  GraphSnapshot,
} from "./types";

// Same-origin by default in production builds; the localhost fallback is dev-only
// so a build missing VITE_API_BASE can never ship pointing at localhost.
const API_BASE =
  import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

/** Single place the access token is attached and an expired session handled.
 *  getAccessToken returns null when auth is not configured. */
async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getAccessToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    // The refresh token is spent or revoked — nothing to retry with.
    signOut();
    notifyUnauthorized();
    throw new Error("Your session has expired. Please sign in again.");
  }
  return res;
}

export async function sendChat(
  message: string,
  conversationId: string,
): Promise<ChatResponse> {
  const res = await apiFetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!res.ok) {
    throw new Error(`The graph service replied with status ${res.status}.`);
  }
  return res.json();
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const res = await apiFetch("/conversations");
  if (!res.ok) {
    throw new Error(`The graph service replied with status ${res.status}.`);
  }
  return res.json();
}

export async function getConversation(
  conversationId: string,
): Promise<ConversationDetail | null> {
  const res = await apiFetch(`/conversations/${encodeURIComponent(conversationId)}`);
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`The graph service replied with status ${res.status}.`);
  }
  return res.json();
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const res = await apiFetch(`/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`The graph service replied with status ${res.status}.`);
  }
}

/** Server-supplied reason if there is one — upload errors are worth reading. */
async function failure(res: Response): Promise<Error> {
  try {
    const body = await res.json();
    const detail = body?.detail ?? body?.error;
    if (typeof detail === "string" && detail) return new Error(detail);
  } catch {
    /* not JSON */
  }
  return new Error(`The graph service replied with status ${res.status}.`);
}

/** The whole knowledge graph — the same nodes and edges the agents traverse. */
export async function getGraph(): Promise<GraphSnapshot> {
  const res = await apiFetch("/graph");
  if (!res.ok) throw await failure(res);
  return res.json();
}

export async function listCVs(): Promise<CVLibrary> {
  const res = await apiFetch("/cvs");
  if (!res.ok) throw await failure(res);
  return res.json();
}

/** Uploads are base64 JSON so the browser talks to the dev server and the
 *  deployed Lambda proxy through the same contract. */
export async function uploadCV(file: File): Promise<CVLibrary> {
  const res = await apiFetch("/cvs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: file.name,
      content_base64: await toBase64(file),
    }),
  });
  if (!res.ok) throw await failure(res);
  return res.json();
}

export async function deleteCV(filename: string): Promise<CVLibrary> {
  const res = await apiFetch(`/cvs/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw await failure(res);
  return res.json();
}

function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.onload = () => {
      const result = String(reader.result);
      resolve(result.slice(result.indexOf(",") + 1));
    };
    reader.readAsDataURL(file);
  });
}

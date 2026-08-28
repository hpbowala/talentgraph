export interface EvidenceRef {
  kind: string;
  detail: string;
  source?: string | null;
}

export interface ChatResponse {
  answer: string;
  intent: string;
  evidence: EvidenceRef[];
  conversation_id: string;
}

export interface Message {
  role: "user" | "assistant" | "error";
  content: string;
  intent?: string;
  evidence?: EvidenceRef[];
}

export interface ConversationSummary {
  conversation_id: string;
  title: string;
  updated_at: string;
}

export interface ConversationTurn {
  user: string;
  answer: string;
  intent: string;
  evidence: EvidenceRef[];
  ts?: string | null;
}

export interface ConversationDetail {
  conversation_id: string;
  title: string;
  turns: ConversationTurn[];
}

export interface CVSummary {
  filename: string;
  size_bytes: number;
  uploaded_at: string;
  person?: string | null;
}

export interface CVLibrary {
  cvs: CVSummary[];
  indexed_at?: string | null;
  /** Notes written by the rebuild that produced this response. */
  note_count?: number | null;
}

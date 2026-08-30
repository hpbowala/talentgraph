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

/** One vault note, as a point in the graph explorer. */
export interface GraphNode {
  id: string;
  type: string;
  /** Connections drawn for this node — drives its radius. */
  degree: number;
  role?: string | null;
  path?: string | null;
}

/** A typed connection between two notes. */
export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  evidence?: string | null;
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** Node count per type. */
  counts: Record<string, number>;
  indexed_at?: string | null;
}

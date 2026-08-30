/** Evidence strings arrive from the backend already formatted as graph walks —
 *  "Alice Perera —HAS_SKILL→ Python", chained for multi-hop paths (see
 *  backend/app/graph/retriever.py). Splitting them back apart lets the note
 *  names become links into the graph explorer. */

export interface EvidenceSegment {
  text: string;
  /** True when this segment is a note name and can be opened in the graph. */
  entity: boolean;
}

// The arrow carries the relation and its direction; capturing it keeps the
// separators in the split output.
const ARROW = /(\s*(?:—[A-Z_]+→|←[A-Z_]+—)\s*)/;

export function parseEvidence(detail: string): EvidenceSegment[] {
  const parts = detail.split(ARROW);
  // No arrows means this is not a relation walk — leave it as plain prose
  // rather than guessing at which words are notes.
  if (parts.length < 3) return [{ text: detail, entity: false }];
  return parts
    .map((part, i) => ({ text: i % 2 === 0 ? part.trim() : part, entity: i % 2 === 0 }))
    .filter((segment) => segment.text.length > 0);
}

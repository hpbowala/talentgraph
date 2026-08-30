/** How each note type and relation is named and coloured, shared so the canvas,
 *  the legend and the detail panel cannot drift apart. */

export const NODE_TYPES = [
  "person",
  "skill",
  "technology",
  "project",
  "domain",
  "education",
  "unknown",
] as const;

export type NodeType = (typeof NODE_TYPES)[number];

/** Hues chosen to stay distinguishable against the near-black canvas. */
export const TYPE_COLOR: Record<string, string> = {
  person: "#8b93f8",
  skill: "#4ecdc4",
  technology: "#f0a868",
  project: "#e879a8",
  domain: "#63b3ed",
  education: "#c084fc",
  unknown: "#6b7280",
};

export const TYPE_LABEL: Record<string, string> = {
  person: "People",
  skill: "Skills",
  technology: "Technologies",
  project: "Projects",
  domain: "Domains",
  education: "Education",
  unknown: "Unresolved",
};

export function typeColor(type: string): string {
  return TYPE_COLOR[type] ?? TYPE_COLOR.unknown;
}

export function typeLabel(type: string): string {
  return TYPE_LABEL[type] ?? type;
}

/** Relation names read as SQL-ish constants in the vault; soften them for the
 *  detail panel while keeping the original visible as the edge label. */
export const RELATION_LABEL: Record<string, string> = {
  HAS_SKILL: "has skill",
  USES: "uses",
  EXPERIENCE_IN: "experience in",
  WORKED_ON: "worked on",
  STUDIED: "studied at",
  IN_DOMAIN: "in domain",
  RELATED_TO: "related to",
};

export function relationLabel(relation: string): string {
  return RELATION_LABEL[relation] ?? relation.toLowerCase().replace(/_/g, " ");
}

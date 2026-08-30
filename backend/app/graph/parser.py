"""Parse the Obsidian vault into nodes and typed edges.

Inverse of app/ingest/vault_writer.py: note type + section heading determine the
relation. Backlink sections are ignored so each relation is created once.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")
HEADING_RE = re.compile(r"^##\s+(.+)$")

# note type -> {section heading -> relation}
SECTION_RELATIONS: dict[str, dict[str, str]] = {
    "person": {
        "Skills": "HAS_SKILL",
        "Technologies": "USES",
        "Domains": "EXPERIENCE_IN",
        "Projects": "WORKED_ON",
        "Education": "STUDIED",
    },
    "project": {
        "Technologies": "USES",
        "Domains": "IN_DOMAIN",
    },
    "skill": {
        "Related Skills": "RELATED_TO",
    },
}


@dataclass
class ParsedNote:
    name: str
    type: str
    path: str
    aliases: list[str] = field(default_factory=list)
    body: str = ""
    role: str = ""  # person notes only — the headline shown in the graph explorer


@dataclass
class ParsedEdge:
    source: str
    target: str
    relation: str
    evidence: str = ""
    source_note: str = ""


def parse_note(path: Path, vault_dir: Path) -> tuple[ParsedNote, list[ParsedEdge]]:
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    note_type = str(post.get("type", "unknown"))
    name = str(post.get("name", path.stem))
    aliases = [str(a) for a in post.get("aliases", []) or []]
    rel_path = str(path.relative_to(vault_dir))
    note = ParsedNote(
        name=name,
        type=note_type,
        path=rel_path,
        aliases=aliases,
        body=post.content,
        role=str(post.get("role") or ""),
    )

    edges: list[ParsedEdge] = []
    relations = SECTION_RELATIONS.get(note_type, {})
    current_relation: str | None = None
    for line in post.content.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            current_relation = relations.get(heading.group(1).strip())
            continue
        if current_relation is None or not line.lstrip().startswith("-"):
            continue
        match = WIKILINK_RE.search(line)
        if not match:
            continue
        target = match.group(1).strip()
        evidence = ""
        if "—" in line:
            evidence = line.split("—", 1)[1].strip().strip('"')
        edges.append(
            ParsedEdge(
                source=name,
                target=target,
                relation=current_relation,
                evidence=evidence,
                source_note=rel_path,
            )
        )
    return note, edges


def parse_vault(vault_dir: Path) -> tuple[list[ParsedNote], list[ParsedEdge]]:
    notes: list[ParsedNote] = []
    edges: list[ParsedEdge] = []
    for path in sorted(vault_dir.rglob("*.md")):
        note, note_edges = parse_note(path, vault_dir)
        notes.append(note)
        edges.extend(note_edges)
    return notes, edges

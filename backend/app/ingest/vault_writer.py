"""Generate the Obsidian vault: Markdown notes with [[Wikilinks]].

The vault IS the knowledge graph. Relation semantics are encoded by note type +
section heading, which the graph parser (app/graph/parser.py) understands:

  Person note:  ## Skills -> HAS_SKILL, ## Technologies -> USES,
                ## Domains -> EXPERIENCE_IN, ## Projects -> WORKED_ON,
                ## Education -> STUDIED
  Project note: ## Technologies -> USES, ## Domains -> IN_DOMAIN
  Skill note:   ## Related Skills -> RELATED_TO

"## People" / "## Projects" sections on non-person notes are backlinks for
Obsidian navigation only; the parser ignores them to avoid duplicate edges.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from app.ingest.normalizer import ALIASES
from app.models import CVProfile

RELATED_SKILL_MIN_SHARED_PEOPLE = 2


def note_name(name: str) -> str:
    """Sanitize an entity name for use as an Obsidian filename and wikilink target."""
    return re.sub(r'[\\/:*?"<>|]', "-", name).strip()


def link(name: str) -> str:
    return f"[[{note_name(name)}]]"


def yaml_str(value: str) -> str:
    """Quote a frontmatter scalar so YAML-significant characters (: # etc.) can't break parsing."""
    return json.dumps(value, ensure_ascii=False)


@dataclass
class VaultIndex:
    """Aggregated cross-CV view used to build entity notes and backlinks."""

    skill_people: dict[str, list[tuple[str, str]]] = field(
        default_factory=lambda: defaultdict(list)
    )  # skill -> [(person, evidence)]
    tech_people: dict[str, list[tuple[str, str]]] = field(default_factory=lambda: defaultdict(list))
    domain_people: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    domain_projects: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    institution_people: dict[str, list[tuple[str, str, int | None]]] = field(
        default_factory=lambda: defaultdict(list)
    )  # institution -> [(person, qualification, year)]
    projects: dict[str, dict] = field(default_factory=dict)  # name -> merged project info
    tech_projects: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))


def build_index(profiles: list[CVProfile]) -> VaultIndex:
    idx = VaultIndex()
    for p in profiles:
        person = p.person_name
        for s in p.skills:
            idx.skill_people[s.name].append((person, s.evidence))
        for t in p.technologies:
            idx.tech_people[t.name].append((person, t.evidence))
        for d in p.domains:
            idx.domain_people[d].append(person)
        for e in p.education:
            idx.institution_people[e.institution].append((person, e.qualification, e.year))
        for proj in p.projects:
            entry = idx.projects.setdefault(
                proj.name,
                {"description": proj.description, "technologies": [], "domains": [], "people": []},
            )
            entry["people"].append(person)
            for t in proj.technologies:
                if t not in entry["technologies"]:
                    entry["technologies"].append(t)
                if proj.name not in idx.tech_projects[t]:
                    idx.tech_projects[t].append(proj.name)
            for d in proj.domains:
                if d not in entry["domains"]:
                    entry["domains"].append(d)
                if proj.name not in idx.domain_projects[d]:
                    idx.domain_projects[d].append(proj.name)
    return idx


def related_skills(idx: VaultIndex) -> dict[str, list[str]]:
    """Skill RELATED_TO Skill when they co-occur in enough people (deterministic)."""
    holders = {skill: {p for p, _ in people} for skill, people in idx.skill_people.items()}
    related: dict[str, list[str]] = defaultdict(list)
    skills = sorted(holders)
    for i, a in enumerate(skills):
        for b in skills[i + 1 :]:
            if len(holders[a] & holders[b]) >= RELATED_SKILL_MIN_SHARED_PEOPLE:
                related[a].append(b)
                related[b].append(a)
    return related


def write_vault(profiles: list[CVProfile], sources: dict[str, str], vault_dir: Path) -> int:
    """Write all notes. `sources` maps person_name -> source CV filename."""
    idx = build_index(profiles)
    related = related_skills(idx)
    count = 0

    for profile in profiles:
        _write(
            vault_dir / "People" / f"{note_name(profile.person_name)}.md",
            person_note(profile, sources.get(profile.person_name, "")),
        )
        count += 1

    for skill, people in sorted(idx.skill_people.items()):
        _write(
            vault_dir / "Skills" / f"{note_name(skill)}.md",
            entity_note("skill", skill, people=people, related=related.get(skill, [])),
        )
        count += 1

    for tech, people in sorted(idx.tech_people.items()):
        _write(
            vault_dir / "Technologies" / f"{note_name(tech)}.md",
            entity_note(
                "technology", tech, people=people, projects=idx.tech_projects.get(tech, [])
            ),
        )
        count += 1

    for name, info in sorted(idx.projects.items()):
        _write(vault_dir / "Projects" / f"{note_name(name)}.md", project_note(name, info))
        count += 1

    for domain, people in sorted(idx.domain_people.items()):
        _write(
            vault_dir / "Domains" / f"{note_name(domain)}.md",
            entity_note(
                "domain",
                domain,
                people=[(p, "") for p in people],
                projects=idx.domain_projects.get(domain, []),
            ),
        )
        count += 1

    for institution, entries in sorted(idx.institution_people.items()):
        _write(
            vault_dir / "Education" / f"{note_name(institution)}.md",
            education_note(institution, entries),
        )
        count += 1

    return count


def person_note(p: CVProfile, source: str) -> str:
    lines = [
        "---",
        "type: person",
        f"name: {yaml_str(p.person_name)}",
        f"role: {yaml_str(p.headline)}",
        f"source: {yaml_str(source)}",
        "---",
        "",
        f"# {p.person_name}",
        "",
        p.summary,
        "",
        "## Skills",
    ]
    lines += [f'- {link(s.name)} — "{s.evidence}"' for s in p.skills]
    lines += ["", "## Technologies"]
    lines += [f'- {link(t.name)} — "{t.evidence}"' for t in p.technologies]
    lines += ["", "## Domains"]
    lines += [f"- {link(d)}" for d in p.domains]
    lines += ["", "## Projects"]
    lines += [f"- {link(proj.name)} — {proj.description}" for proj in p.projects]
    lines += ["", "## Education"]
    lines += [
        f"- {link(e.institution)} — {e.qualification}" + (f" ({e.year})" if e.year else "")
        for e in p.education
    ]
    lines += ["", "## Experience"]
    for e in p.experience:
        period = f"{e.start_year or '?'}–{e.end_year or 'present'}"
        lines.append(f"- {e.role} at {e.organization} ({period}): {e.summary}")
    return "\n".join(lines) + "\n"


def entity_note(
    note_type: str,
    name: str,
    *,
    people: list[tuple[str, str]],
    related: list[str] | None = None,
    projects: list[str] | None = None,
) -> str:
    lines = ["---", f"type: {note_type}", f"name: {yaml_str(name)}"]
    aliases = [a for a in ALIASES.get(name, []) if a.lower() != name.lower()]
    if aliases:
        lines.append("aliases:")
        lines += [f"  - {yaml_str(a)}" for a in aliases]
    lines += ["---", "", f"# {name}", "", "## People"]
    for person, evidence in people:
        lines.append(f"- {link(person)}" + (f' — "{evidence}"' if evidence else ""))
    if projects:
        lines += ["", "## Projects"]
        lines += [f"- {link(proj)}" for proj in projects]
    if related:
        lines += ["", "## Related Skills"]
        lines += [f"- {link(r)}" for r in sorted(related)]
    return "\n".join(lines) + "\n"


def project_note(name: str, info: dict) -> str:
    lines = [
        "---",
        "type: project",
        f"name: {yaml_str(name)}",
        "---",
        "",
        f"# {name}",
        "",
        info["description"],
        "",
        "## Technologies",
    ]
    lines += [f"- {link(t)}" for t in info["technologies"]]
    lines += ["", "## Domains"]
    lines += [f"- {link(d)}" for d in info["domains"]]
    lines += ["", "## People"]
    lines += [f"- {link(p)}" for p in info["people"]]
    return "\n".join(lines) + "\n"


def education_note(institution: str, entries: list[tuple[str, str, int | None]]) -> str:
    lines = [
        "---",
        "type: education",
        f"name: {yaml_str(institution)}",
        "---",
        "",
        f"# {institution}",
        "",
        "## People",
    ]
    for person, qualification, year in entries:
        suffix = f" ({year})" if year else ""
        lines.append(f"- {link(person)} — {qualification}{suffix}")
    return "\n".join(lines) + "\n"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

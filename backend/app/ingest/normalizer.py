"""Entity normalization: map surface forms to canonical entity names.

Two layers:
1. A deterministic alias table (primary mechanism, unit-testable).
2. An optional LLM merge pass over the union of remaining names to catch
   variants the table does not know (run once per ingestion, cached on disk).
"""

from pydantic import BaseModel, Field

from app.llm.provider import LLMProvider
from app.models import CVProfile

# canonical name -> lowercase surface forms that map to it
ALIASES: dict[str, list[str]] = {
    "AWS": ["aws", "amazon web services", "aws cloud"],
    "NLP": ["nlp", "natural language processing"],
    "React": ["react", "reactjs", "react.js"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"],
    "API design": [
        "api design",
        "rest api design",
        "application programming interface design",
        "application programming interface",
    ],
    "Machine Learning": ["machine learning", "ml", "basic machine learning"],
    "CI/CD": ["ci/cd", "ci/cd automation", "cicd", "continuous integration"],
    "Kubernetes": ["kubernetes", "k8s"],
    "PostgreSQL": ["postgresql", "postgres"],
    "Artificial Intelligence": ["artificial intelligence", "ai"],
    "Infrastructure as Code": ["infrastructure as code", "iac"],
    "SQL": ["sql"],
    "Python": ["python"],
}

_SURFACE_TO_CANONICAL = {
    surface: canonical for canonical, surfaces in ALIASES.items() for surface in surfaces
}


def normalize_name(name: str) -> str:
    """Deterministic normalization of a single entity name."""
    cleaned = " ".join(name.strip().split())
    canonical = _SURFACE_TO_CANONICAL.get(cleaned.lower())
    if canonical:
        return canonical
    # Strip parenthetical qualifiers like "Python (expert)" and retry.
    if "(" in cleaned:
        base = cleaned.split("(")[0].strip()
        canonical = _SURFACE_TO_CANONICAL.get(base.lower())
        if canonical:
            return canonical
        cleaned = base
    return cleaned


class MergePair(BaseModel):
    surface: str = Field(description="A name that is a duplicate/variant of another")
    canonical: str = Field(description="The canonical name it should be merged into")


class MergeMapping(BaseModel):
    """LLM output: surface form -> canonical name for residual duplicates."""

    merges: list[MergePair] = Field(
        description=(
            "One entry per duplicate/variant name. Names that are already unique must NOT appear."
        )
    )


MERGE_SYSTEM_PROMPT = """\
You are an entity normalization system for a workforce knowledge graph. You are
given a list of entity names (skills, technologies, domains) that were extracted
from CVs. Identify names that refer to the same real-world entity (abbreviation vs
full form, spelling variants, singular/plural) and map each variant to a single
canonical name. Prefer the widely used short form as canonical (e.g. "AWS", "NLP").
Do not merge genuinely different entities. If nothing needs merging, return an
empty mapping.
"""


def llm_merge_pass(names: set[str], provider: LLMProvider) -> dict[str, str]:
    """One LLM call over the union of entity names; returns surface->canonical."""
    result = provider.parse(
        system=MERGE_SYSTEM_PROMPT,
        user="Entity names:\n" + "\n".join(f"- {n}" for n in sorted(names)),
        schema=MergeMapping,
    )
    # Never let the LLM rename something the deterministic table already owns.
    return {
        pair.surface: pair.canonical
        for pair in result.merges
        if pair.surface.lower() not in _SURFACE_TO_CANONICAL and pair.surface != pair.canonical
    }


def normalize_profile(profile: CVProfile, extra_mapping: dict[str, str] | None = None) -> CVProfile:
    """Return a copy of the profile with all entity names normalized."""
    mapping = extra_mapping or {}

    def norm(name: str) -> str:
        name = normalize_name(name)
        return mapping.get(name, name)

    updated = profile.model_copy(deep=True)
    # PDFs often render names in caps ("ALICE PERERA"); title-case them.
    if updated.person_name.isupper():
        updated.person_name = updated.person_name.title()
    for item in updated.skills:
        item.name = norm(item.name)
    for item in updated.technologies:
        item.name = norm(item.name)
    updated.domains = _dedupe([norm(d) for d in updated.domains])
    for project in updated.projects:
        project.technologies = _dedupe([norm(t) for t in project.technologies])
        project.domains = _dedupe([norm(d) for d in project.domains])
    # Dedupe skills/technologies that collapsed to the same canonical name.
    updated.skills = _dedupe_items(updated.skills)
    updated.technologies = _dedupe_items(updated.technologies)
    return updated


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for name in names:
        seen.setdefault(name, None)
    return list(seen)


def _dedupe_items(items):
    seen: dict[str, None] = {}
    result = []
    for item in items:
        if item.name not in seen:
            seen[item.name] = None
            result.append(item)
    return result

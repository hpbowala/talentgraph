"""CV -> vault build, shared by the ingestion CLI and the /cvs API.

One pass over the corpus: extract each CV into a CVProfile, normalize entity
names across all of them, then regenerate the vault from scratch so entities
belonging only to a removed CV disappear with it.
"""

import shutil
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from app.cv_store import VAULT_SUBDIRS, content_digest
from app.ingest.extract_text import extract_text
from app.ingest.extraction_agent import extract_profile
from app.ingest.normalizer import llm_merge_pass, normalize_profile
from app.ingest.vault_writer import write_vault
from app.llm.provider import LLMProvider
from app.models import CVProfile

# Extraction is one API call per CV and nothing shares state, so a rebuild after
# an upload is bounded by the slowest CV rather than by their sum.
EXTRACT_WORKERS = 4


@dataclass
class BuildReport:
    profiles: list[CVProfile] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)  # person -> CV filename
    note_count: int = 0
    extracted: list[str] = field(default_factory=list)  # CVs that needed an LLM call
    reused: list[str] = field(default_factory=list)  # CVs served from the profile cache


def _noop(_: str) -> None:
    pass


def build_profiles(
    cv_paths: list[Path],
    provider: LLMProvider,
    *,
    use_cache: bool = True,
    merge: bool = True,
    profile_cache=None,
    log: Callable[[str], None] = _noop,
) -> BuildReport:
    """Extract and normalize every CV. `profile_cache` (app.cv_store.ProfileCache)
    keys raw extractions by file content so unchanged CVs cost nothing."""
    report = BuildReport()

    def extract(path: Path) -> tuple[CVProfile, bool]:
        """(profile, came_from_cache) for one CV."""
        digest = None
        if profile_cache is not None:
            digest = content_digest(path.read_bytes())
            cached = profile_cache.get(digest)
            if cached is not None:
                return cached, True
        profile = extract_profile(extract_text(path), provider, use_cache=use_cache)
        if profile_cache is not None and digest is not None:
            profile_cache.put(digest, profile)
        return profile, False

    with ThreadPoolExecutor(max_workers=EXTRACT_WORKERS) as pool:
        extracted = list(pool.map(extract, cv_paths))

    for path, (profile, from_cache) in zip(cv_paths, extracted, strict=True):
        if from_cache:
            report.reused.append(path.name)
            log(f"  cached    {profile.person_name:<24} <- {path.name}")
        else:
            report.extracted.append(path.name)
            log(
                f"  extracted {profile.person_name:<24} <- {path.name} "
                f"({len(profile.skills)} skills, {len(profile.projects)} projects)"
            )
        report.profiles.append(profile)

    # Deterministic normalization first, then one LLM pass over leftover names.
    report.profiles = [normalize_profile(p) for p in report.profiles]
    if merge and report.profiles:
        names = {item.name for p in report.profiles for item in (*p.skills, *p.technologies)} | {
            d for p in report.profiles for d in p.domains
        }
        extra = llm_merge_pass(names, provider)
        if extra:
            log(f"  LLM merge pass: {extra}")
            report.profiles = [normalize_profile(p, extra) for p in report.profiles]

    # Keyed only once names are final: normalization rewrites person_name (a CV
    # read as "ALICE PERERA" becomes "Alice Perera"), and the vault writer and
    # the /cvs library both look these up by the normalized name.
    report.sources = {
        profile.person_name: path.name
        for profile, path in zip(report.profiles, cv_paths, strict=True)
    }
    return report


def rebuild_vault(
    cv_paths: list[Path],
    vault_dir: Path,
    provider: LLMProvider,
    *,
    use_cache: bool = True,
    merge: bool = True,
    profile_cache=None,
    log: Callable[[str], None] = _noop,
) -> BuildReport:
    report = build_profiles(
        cv_paths,
        provider,
        use_cache=use_cache,
        merge=merge,
        profile_cache=profile_cache,
        log=log,
    )
    for sub in VAULT_SUBDIRS:
        shutil.rmtree(vault_dir / sub, ignore_errors=True)
    report.note_count = write_vault(report.profiles, report.sources, vault_dir)
    return report

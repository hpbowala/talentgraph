"""Rebuild the knowledge graph from the CV corpus.

Called by the /cvs API after an upload or delete. Serialized with a lock so two
concurrent uploads cannot interleave two rebuilds of the same vault.
"""

import threading
from collections.abc import Callable
from pathlib import Path

from app import cv_store
from app.graph.loader import install_graph
from app.graph.model import KnowledgeGraph
from app.ingest.extract_text import discover_cvs
from app.ingest.pipeline import BuildReport, rebuild_vault
from app.llm.provider import LLMProvider

_lock = threading.Lock()


def _noop(_: str) -> None:
    pass


def reindex(provider: LLMProvider | None = None, log: Callable[[str], None] = _noop) -> BuildReport:
    """Rebuild the vault from every CV in the store and reload the live graph."""
    with _lock:
        provider = provider or LLMProvider()
        with cv_store.checkout() as (cv_dir, vault_dir):
            cv_paths = discover_cvs(cv_dir)
            log(f"Indexing {len(cv_paths)} CVs from {cv_store.backend()} storage")
            report = rebuild_vault(
                cv_paths,
                vault_dir,
                provider,
                profile_cache=cv_store.ProfileCache(),
                log=log,
            )
            stamp = cv_store.publish_vault(vault_dir, report.sources)
            log(f"Published {report.note_count} notes ({stamp})")
            # Adopt the vault we just built rather than re-reading it from S3.
            install_graph(KnowledgeGraph.from_vault(vault_dir), stamp)
        return report


def cv_person_names() -> dict[str, str]:
    """CV filename -> the person the last build extracted from it."""
    sources: dict[str, str] = cv_store.read_manifest().get("sources", {})
    return {filename: person for person, filename in sources.items()}


def local_vault_path() -> Path:
    return cv_store.local_vault_dir()

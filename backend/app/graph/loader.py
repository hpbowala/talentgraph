"""Load the knowledge graph from the local vault or from S3 (VAULT_SOURCE seam)."""

import os
import tempfile
from pathlib import Path

from app.graph.model import KnowledgeGraph

REPO_ROOT = Path(__file__).resolve().parents[3]

_cached: KnowledgeGraph | None = None
_cached_stamp: str | None = None


def load_graph(force_reload: bool = False) -> KnowledgeGraph:
    """Module-level cache: build once per process (cold start), reuse per request."""
    global _cached
    if _cached is None or force_reload:
        _cached = KnowledgeGraph.from_vault(_vault_dir())
    return _cached


def install_graph(graph: KnowledgeGraph, stamp: str | None = None) -> None:
    """Adopt a graph built in this process (see app/ingest/reindex.py) instead of
    re-reading the vault we just wrote."""
    global _cached, _cached_stamp
    _cached, _cached_stamp = graph, stamp


def cached_stamp() -> str | None:
    """Index stamp of the in-process graph, if it was installed with one."""
    return _cached_stamp


def _vault_dir() -> Path:
    source = os.getenv("VAULT_SOURCE", "local")
    if source == "local":
        return Path(os.getenv("VAULT_DIR", REPO_ROOT / "vault"))
    if source == "s3":
        return _download_vault_from_s3()
    raise ValueError(f"Unknown VAULT_SOURCE: {source}")


def _download_vault_from_s3() -> Path:
    import boto3  # noqa: PLC0415 — only needed in cloud mode

    bucket = os.environ["VAULT_BUCKET"]
    target = Path(tempfile.mkdtemp(prefix="talentgraph-vault-"))
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=bucket, Prefix="vault/"):
        for obj in page.get("Contents", []):
            rel = obj["Key"].removeprefix("vault/")
            if not rel or rel.endswith("/"):
                continue
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, obj["Key"], str(dest))
            count += 1
    if count == 0:
        raise RuntimeError(f"No vault notes found under s3://{bucket}/vault/")
    return target

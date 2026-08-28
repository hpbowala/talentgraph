"""Ingestion CLI: CVs -> extraction -> normalization -> Obsidian vault (-> S3).

Run from backend/: uv run talentgraph-ingest [--upload]

The same pipeline runs behind the /cvs API when a CV is uploaded or deleted
through the app (app/ingest/reindex.py).
"""

import argparse
from pathlib import Path

from app.cv_store import ProfileCache, write_manifest
from app.ingest.extract_text import discover_cvs
from app.ingest.pipeline import rebuild_vault
from app.llm.provider import LLMProvider

REPO_ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest CVs into the Obsidian knowledge vault")
    parser.add_argument("--cv-dir", type=Path, default=REPO_ROOT / "data" / "sample_cvs")
    parser.add_argument("--vault-dir", type=Path, default=REPO_ROOT / "vault")
    parser.add_argument("--no-cache", action="store_true", help="Bypass the LLM response cache")
    parser.add_argument("--no-merge", action="store_true", help="Skip the LLM merge pass")
    parser.add_argument("--upload", action="store_true", help="Sync CVs and vault to S3")
    args = parser.parse_args()

    provider = LLMProvider()

    cv_paths = discover_cvs(args.cv_dir)
    if not cv_paths:
        raise SystemExit(f"No CVs found in {args.cv_dir}")
    print(f"Found {len(cv_paths)} CVs in {args.cv_dir} (model: {provider.model})")

    report = rebuild_vault(
        cv_paths,
        args.vault_dir,
        provider,
        use_cache=not args.no_cache,
        merge=not args.no_merge,
        profile_cache=ProfileCache(),
        log=print,
    )
    stamp = write_manifest(args.vault_dir, report.sources)
    print(f"Wrote {report.note_count} notes to {args.vault_dir} ({stamp})")

    if args.upload:
        from app.ingest.s3_sync import upload_cvs_and_vault  # noqa: PLC0415

        upload_cvs_and_vault(args.cv_dir, args.vault_dir)


if __name__ == "__main__":
    main()

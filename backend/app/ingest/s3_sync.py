"""Upload source CVs, their cached extractions and the generated vault to S3.

profiles/ goes too, or the first upload re-extracts the whole corpus.
"""

import os
from pathlib import Path

import boto3

from app.cv_store import MANIFEST_NAME, local_profile_dir


def upload_cvs_and_vault(cv_dir: Path, vault_dir: Path) -> None:
    bucket = os.getenv("VAULT_BUCKET")
    if not bucket:
        raise SystemExit("Set VAULT_BUCKET to the TalentGraph data bucket name before --upload")

    s3 = boto3.client("s3")
    cv_paths = [
        p
        for p in sorted(cv_dir.glob("*"))
        if p.is_file() and p.suffix.lower() in {".pdf", ".txt", ".md"}
    ]
    vault_paths = sorted(vault_dir.rglob("*.md"))
    manifest = vault_dir / MANIFEST_NAME
    if manifest.exists():
        vault_paths.append(manifest)
    profile_dir = local_profile_dir()
    profile_paths = sorted(profile_dir.glob("*.json")) if profile_dir.exists() else []
    total = len(cv_paths) + len(vault_paths) + len(profile_paths)
    print(
        f"Uploading {total} files to s3://{bucket}/ "
        f"({len(cv_paths)} CVs, {len(vault_paths)} vault notes, "
        f"{len(profile_paths)} cached profiles)",
        flush=True,
    )

    uploaded = 0
    for path in cv_paths:
        s3.upload_file(str(path), bucket, f"cvs/{path.name}")
        uploaded += 1
        print(f"  [{uploaded}/{total}] cvs/{path.name}", flush=True)
    for path in vault_paths:
        key = f"vault/{path.relative_to(vault_dir)}"
        s3.upload_file(str(path), bucket, key)
        uploaded += 1
        print(f"  [{uploaded}/{total}] {key}", flush=True)
    for path in profile_paths:
        s3.upload_file(str(path), bucket, f"profiles/{path.name}")
        uploaded += 1
        print(f"  [{uploaded}/{total}] profiles/{path.name}", flush=True)
    print(f"Uploaded {uploaded} files to s3://{bucket}/")

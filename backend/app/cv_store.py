"""Storage for the CV corpus and the vault it compiles into.

Two backends, selected by CV_STORE (defaults to VAULT_SOURCE):

- "s3":    s3://$VAULT_BUCKET/{cvs,vault,profiles}/   (deployed default)
- "local": data/sample_cvs/ + vault/ on disk          (development)

    cvs/<filename>            uploaded CV documents — the source of truth
    vault/<Type>/<Note>.md    generated knowledge-graph notes
    vault/.index.json         manifest: build stamp + person -> CV filename
    profiles/<sha256>.json    cached LLM extraction, keyed by CV file content

The manifest stamp is also how instances notice another one's upload.
"""

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.models import CVProfile

REPO_ROOT = Path(__file__).resolve().parents[2]

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md"}
MAX_CV_BYTES = 4 * 1024 * 1024

# The note categories the vault is made of; a rebuild replaces all of them.
VAULT_SUBDIRS = ("People", "Skills", "Technologies", "Projects", "Domains", "Education")

CV_PREFIX = "cvs/"
VAULT_PREFIX = "vault/"
PROFILE_PREFIX = "profiles/"
MANIFEST_NAME = ".index.json"

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._ -]")


class CVStoreError(Exception):
    """A caller mistake (bad filename, unsupported type, oversized upload)."""


@dataclass(frozen=True)
class CVRecord:
    filename: str
    size_bytes: int
    uploaded_at: str


def backend() -> str:
    return os.getenv("CV_STORE") or os.getenv("VAULT_SOURCE", "local")


def _bucket() -> str:
    bucket = os.getenv("VAULT_BUCKET")
    if not bucket:
        raise RuntimeError("VAULT_BUCKET must be set when the CV store is backed by S3")
    return bucket


def _s3():
    import boto3  # noqa: PLC0415 — only needed in cloud mode

    return boto3.client("s3")


def local_cv_dir() -> Path:
    return Path(os.getenv("CV_DIR", REPO_ROOT / "data" / "sample_cvs"))


def local_vault_dir() -> Path:
    return Path(os.getenv("VAULT_DIR", REPO_ROOT / "vault"))


def local_profile_dir() -> Path:
    return Path(os.getenv("PROFILE_CACHE_DIR", REPO_ROOT / ".cache" / "profiles"))


# ---------- validation ----------


def safe_filename(name: str) -> str:
    """Reduce an uploaded name to a flat, storage-safe filename."""
    candidate = _UNSAFE_CHARS.sub("_", Path(name.replace("\\", "/")).name).strip(" .")
    if not candidate:
        raise CVStoreError("The uploaded file needs a name.")
    if Path(candidate).suffix.lower() not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise CVStoreError(f"Unsupported CV format — upload one of: {supported}.")
    return candidate


def check_size(content: bytes) -> None:
    if not content:
        raise CVStoreError("The uploaded file is empty.")
    if len(content) > MAX_CV_BYTES:
        raise CVStoreError(f"CVs must be smaller than {MAX_CV_BYTES // (1024 * 1024)} MB.")


# ---------- CV documents ----------


def list_cvs() -> list[CVRecord]:
    if backend() == "local":
        cv_dir = local_cv_dir()
        if not cv_dir.exists():
            return []
        records = [
            CVRecord(
                filename=path.name,
                size_bytes=path.stat().st_size,
                uploaded_at=datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
                    timespec="seconds"
                ),
            )
            for path in sorted(cv_dir.iterdir())
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        ]
    else:
        s3, bucket = _s3(), _bucket()
        records = []
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=CV_PREFIX):
            for obj in page.get("Contents", []):
                name = obj["Key"].removeprefix(CV_PREFIX)
                if not name or name.endswith("/"):
                    continue
                records.append(
                    CVRecord(
                        filename=name,
                        size_bytes=obj["Size"],
                        uploaded_at=obj["LastModified"]
                        .astimezone(UTC)
                        .isoformat(timespec="seconds"),
                    )
                )
    return sorted(records, key=lambda r: r.filename.lower())


def put_cv(filename: str, content: bytes) -> CVRecord:
    """Store an uploaded CV, replacing any existing file of the same name."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    if backend() == "local":
        cv_dir = local_cv_dir()
        cv_dir.mkdir(parents=True, exist_ok=True)
        (cv_dir / filename).write_bytes(content)
    else:
        _s3().put_object(Bucket=_bucket(), Key=f"{CV_PREFIX}{filename}", Body=content)
    return CVRecord(filename=filename, size_bytes=len(content), uploaded_at=now)


def delete_cv(filename: str) -> bool:
    """Remove a CV. Returns False if it was not in the store."""
    if backend() == "local":
        path = local_cv_dir() / filename
        if not path.is_file():
            return False
        path.unlink()
        return True
    s3, bucket, key = _s3(), _bucket(), f"{CV_PREFIX}{filename}"
    from botocore.exceptions import ClientError  # noqa: PLC0415

    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as err:
        if err.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise
    s3.delete_object(Bucket=bucket, Key=key)
    return True


# ---------- extraction cache (keyed by CV content) ----------


def content_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class ProfileCache:
    """Caches the raw LLM extraction per CV file, so re-indexing after an upload
    only pays for the new document. Normalization is re-applied every build."""

    def get(self, digest: str) -> CVProfile | None:
        raw = self._read(f"{digest}.json")
        return CVProfile.model_validate_json(raw) if raw else None

    def put(self, digest: str, profile: CVProfile) -> None:
        self._write(f"{digest}.json", profile.model_dump_json())

    def _read(self, name: str) -> str | None:
        if backend() == "local":
            path = local_profile_dir() / name
            return path.read_text(encoding="utf-8") if path.exists() else None
        from botocore.exceptions import ClientError  # noqa: PLC0415

        try:
            obj = _s3().get_object(Bucket=_bucket(), Key=f"{PROFILE_PREFIX}{name}")
        except ClientError as err:
            if err.response["Error"]["Code"] in {"NoSuchKey", "404", "NotFound"}:
                return None
            raise
        return obj["Body"].read().decode("utf-8")

    def _write(self, name: str, body: str) -> None:
        if backend() == "local":
            path = local_profile_dir() / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            return
        _s3().put_object(
            Bucket=_bucket(),
            Key=f"{PROFILE_PREFIX}{name}",
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )


# ---------- vault build workspace ----------


@contextmanager
def checkout() -> Iterator[tuple[Path, Path]]:
    """Yield (cv_dir, vault_dir) for a rebuild.

    Built in a scratch directory and only made live by publish_vault(), so a
    half-failed run leaves the current graph intact.
    """
    workspace = Path(tempfile.mkdtemp(prefix="talentgraph-build-"))
    try:
        vault_dir = workspace / "vault"
        vault_dir.mkdir(parents=True)
        if backend() == "local":
            cv_dir = local_cv_dir()
            cv_dir.mkdir(parents=True, exist_ok=True)
        else:
            cv_dir = workspace / "cvs"
            cv_dir.mkdir(parents=True)
            _download_cvs(cv_dir)
        yield cv_dir, vault_dir
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _download_cvs(dest: Path) -> None:
    s3, bucket = _s3(), _bucket()
    keys = [
        obj["Key"]
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=CV_PREFIX)
        for obj in page.get("Contents", [])
        if not obj["Key"].endswith("/")
    ]
    _in_parallel(
        lambda key: s3.download_file(bucket, key, str(dest / Path(key).name)),
        keys,
    )


def manifest_body(sources: dict[str, str]) -> tuple[str, str]:
    """(stamp, JSON body) for a manifest describing a just-built vault."""
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    return stamp, json.dumps({"stamp": stamp, "sources": sources}, indent=2, sort_keys=True)


def write_manifest(vault_dir: Path, sources: dict[str, str]) -> str:
    """Write the manifest into a vault directory on disk. Returns the new stamp."""
    stamp, body = manifest_body(sources)
    (vault_dir / MANIFEST_NAME).write_text(body, encoding="utf-8")
    return stamp


def publish_vault(vault_dir: Path, sources: dict[str, str]) -> str:
    """Make the freshly built vault the live one and return its new stamp.

    Manifest written last, so a reader sees either the old index or the new.
    """
    if backend() == "local":
        return _publish_local(vault_dir, sources)

    stamp, manifest = manifest_body(sources)

    s3, bucket = _s3(), _bucket()
    notes = sorted(vault_dir.rglob("*.md"))
    fresh_keys = {f"{VAULT_PREFIX}{p.relative_to(vault_dir).as_posix()}" for p in notes}
    _in_parallel(
        lambda path: s3.upload_file(
            str(path), bucket, f"{VAULT_PREFIX}{path.relative_to(vault_dir).as_posix()}"
        ),
        notes,
    )

    manifest_key = f"{VAULT_PREFIX}{MANIFEST_NAME}"
    stale = [
        obj["Key"]
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=VAULT_PREFIX)
        for obj in page.get("Contents", [])
        if obj["Key"] not in fresh_keys and obj["Key"] != manifest_key
    ]
    for batch in (stale[i : i + 1000] for i in range(0, len(stale), 1000)):
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in batch]})

    s3.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=manifest.encode("utf-8"),
        ContentType="application/json",
    )
    return stamp


def _publish_local(vault_dir: Path, sources: dict[str, str]) -> str:
    """Swap the built categories into the live vault, leaving anything else in
    there (an .obsidian workspace, say) alone."""
    target = local_vault_dir()
    target.mkdir(parents=True, exist_ok=True)
    for sub in VAULT_SUBDIRS:
        shutil.rmtree(target / sub, ignore_errors=True)
    for built in sorted(p for p in vault_dir.iterdir() if p.is_dir()):
        shutil.copytree(built, target / built.name)
    return write_manifest(target, sources)


def read_manifest() -> dict:
    """The live index manifest ({} when the vault predates manifests)."""
    if backend() == "local":
        path = local_vault_dir() / MANIFEST_NAME
        if not path.exists():
            return {}
        raw = path.read_text(encoding="utf-8")
    else:
        from botocore.exceptions import ClientError  # noqa: PLC0415

        try:
            obj = _s3().get_object(Bucket=_bucket(), Key=f"{VAULT_PREFIX}{MANIFEST_NAME}")
        except ClientError as err:
            if err.response["Error"]["Code"] in {"NoSuchKey", "404", "NotFound"}:
                return {}
            raise
        raw = obj["Body"].read().decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def index_stamp() -> str | None:
    """Identity of the published index; changes whenever the vault is rebuilt."""
    return read_manifest().get("stamp")


def _in_parallel(fn, items: list) -> None:
    if not items:
        return
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    with ThreadPoolExecutor(max_workers=16) as pool:
        for _ in pool.map(fn, items):
            pass

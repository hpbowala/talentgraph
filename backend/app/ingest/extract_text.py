"""Extract raw text from CV documents (PDF via pypdf, plain text otherwise)."""

from pathlib import Path

from pypdf import PdfReader

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md"}


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if path.suffix.lower() in SUPPORTED_SUFFIXES:
        return path.read_text(encoding="utf-8")
    raise ValueError(f"Unsupported CV format: {path.name}")


def discover_cvs(cv_dir: Path) -> list[Path]:
    """Find CV files, deduplicating by stem (prefer .pdf to exercise the PDF path)."""
    by_stem: dict[str, Path] = {}
    for path in sorted(cv_dir.iterdir()):
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        existing = by_stem.get(path.stem)
        if existing is None or path.suffix.lower() == ".pdf":
            by_stem[path.stem] = path
    return sorted(by_stem.values())

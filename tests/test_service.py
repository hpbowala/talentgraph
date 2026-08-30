"""Unit tests for app.service: title derivation, turn -> history flattening, and
the validation an uploaded CV passes before it reaches the store.
"""

import pytest

from app import cv_store, service
from app.service import TITLE_MAX_CHARS, derive_title, history_from_turns


def test_derive_title_short_message_kept_verbatim():
    assert derive_title("Who has Python experience?") == "Who has Python experience?"


def test_derive_title_collapses_whitespace():
    assert derive_title("  Who   has\nPython? ") == "Who has Python?"


def test_derive_title_truncates_long_messages():
    title = derive_title("x" * 200)
    assert len(title) <= TITLE_MAX_CHARS
    assert title.endswith("…")


def test_derive_title_empty_message_falls_back():
    assert derive_title("   ") == "New conversation"


def test_history_from_turns_projects_llm_fields():
    turns = [
        {
            "user": "Who knows Python?",
            "answer": "Alice does.",
            "intent": "SKILL",
            "evidence": [{"kind": "relation", "detail": "Alice —HAS_SKILL→ Python"}],
            "entities": ["Alice Perera", "Python"],
            "ts": "2026-08-28T10:00:00+00:00",
        }
    ]
    assert history_from_turns(turns) == [
        {
            "user": "Who knows Python?",
            "answer": "Alice does.",
            "entities": ["Alice Perera", "Python"],
        }
    ]


def test_history_from_turns_tolerates_missing_fields():
    assert history_from_turns([{"user": "hi"}]) == [{"user": "hi", "answer": "", "entities": []}]


@pytest.fixture()
def local_store(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_STORE", "local")
    monkeypatch.setenv("CV_DIR", str(tmp_path / "cvs"))
    monkeypatch.setenv("VAULT_DIR", str(tmp_path / "vault"))
    (tmp_path / "vault").mkdir()
    return tmp_path


CV_TEXT = b"""Ravi Kumar
Backend Engineer

Skills
- Python: built the ingestion service in Python.
- AWS: ran the platform on AWS for four years.
"""


def test_add_cv_stores_the_document_and_lists_it(local_store):
    library = service.add_cv("ravi_kumar.txt", CV_TEXT)

    assert [cv.filename for cv in library.cvs] == ["ravi_kumar.txt"]
    assert (local_store / "cvs" / "ravi_kumar.txt").read_bytes() == CV_TEXT
    # Indexing happens separately, so nothing is attributed to a person yet.
    assert library.cvs[0].person is None
    assert library.indexed_at is None


def test_add_cv_rejects_a_document_with_no_readable_text(local_store):
    with pytest.raises(cv_store.CVStoreError):
        service.add_cv("scan.txt", b"CV\n")
    assert not (local_store / "cvs" / "scan.txt").exists()


def test_add_cv_rejects_an_unsupported_format(local_store):
    with pytest.raises(cv_store.CVStoreError):
        service.add_cv("resume.docx", CV_TEXT)


def test_delete_cv_reports_an_unknown_filename(local_store):
    with pytest.raises(cv_store.CVStoreError):
        service.delete_cv("nobody.txt")


def test_delete_cv_removes_the_document(local_store):
    service.add_cv("ravi_kumar.txt", CV_TEXT)
    library = service.delete_cv("ravi_kumar.txt")

    assert library.cvs == []
    assert not (local_store / "cvs" / "ravi_kumar.txt").exists()

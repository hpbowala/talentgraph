"""Unit tests for the local CV store: name safety, limits, and the round trip
between the stored corpus and the index manifest the UI reads.

The S3 backend is exercised manually against AWS.
"""

import pytest

from app import cv_store


@pytest.fixture(autouse=True)
def local_store(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_STORE", "local")
    monkeypatch.setenv("CV_DIR", str(tmp_path / "cvs"))
    monkeypatch.setenv("VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setenv("PROFILE_CACHE_DIR", str(tmp_path / "profiles"))
    (tmp_path / "vault").mkdir()
    return tmp_path


def test_safe_filename_keeps_a_plain_name():
    assert cv_store.safe_filename("alice_perera.pdf") == "alice_perera.pdf"


def test_safe_filename_strips_directory_traversal():
    assert cv_store.safe_filename("../../etc/passwd.txt") == "passwd.txt"
    assert cv_store.safe_filename("C:\\Users\\me\\cv.pdf") == "cv.pdf"


def test_safe_filename_replaces_awkward_characters():
    assert cv_store.safe_filename("a?b*c.md") == "a_b_c.md"


def test_safe_filename_rejects_unsupported_formats():
    with pytest.raises(cv_store.CVStoreError):
        cv_store.safe_filename("resume.docx")


def test_safe_filename_rejects_a_nameless_upload():
    with pytest.raises(cv_store.CVStoreError):
        cv_store.safe_filename("   ")


def test_check_size_rejects_empty_and_oversized_uploads():
    with pytest.raises(cv_store.CVStoreError):
        cv_store.check_size(b"")
    with pytest.raises(cv_store.CVStoreError):
        cv_store.check_size(b"x" * (cv_store.MAX_CV_BYTES + 1))
    cv_store.check_size(b"x" * 1024)  # within the limit


def test_put_list_and_delete_round_trip():
    cv_store.put_cv("ravi.txt", b"Ravi Kumar\nBackend engineer")
    cv_store.put_cv("alice.md", b"Alice Perera")

    listed = cv_store.list_cvs()
    assert [r.filename for r in listed] == ["alice.md", "ravi.txt"]
    assert listed[1].size_bytes == len(b"Ravi Kumar\nBackend engineer")

    assert cv_store.delete_cv("ravi.txt") is True
    assert [r.filename for r in cv_store.list_cvs()] == ["alice.md"]
    # Deleting something that is not there is reported, not raised.
    assert cv_store.delete_cv("ravi.txt") is False


def test_listing_ignores_unsupported_files(local_store):
    cv_store.put_cv("alice.md", b"Alice Perera")
    (local_store / "cvs" / "notes.docx").write_bytes(b"not a CV")
    assert [r.filename for r in cv_store.list_cvs()] == ["alice.md"]


def test_manifest_round_trip_carries_the_stamp_and_sources(local_store):
    stamp = cv_store.write_manifest(local_store / "vault", {"Alice Perera": "alice.md"})
    assert cv_store.index_stamp() == stamp
    assert cv_store.read_manifest()["sources"] == {"Alice Perera": "alice.md"}


def test_index_stamp_is_none_before_the_first_build():
    assert cv_store.index_stamp() is None


def test_profile_cache_round_trip(sample_profiles):
    cache = cv_store.ProfileCache()
    digest = cv_store.content_digest(b"cv bytes")
    assert cache.get(digest) is None

    cache.put(digest, sample_profiles[0])
    assert cache.get(digest).person_name == sample_profiles[0].person_name

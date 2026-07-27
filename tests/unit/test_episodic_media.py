"""Unit tests for the content-addressed media blob store."""

from pathlib import Path

import pytest

from memory.episodic_memory.media import MediaRef, path_for_hash, store_bytes


@pytest.mark.unit
def test_store_bytes_writes_file_and_returns_ref(tmp_path):
    ref = store_bytes(b"hello world", "image/png", tmp_path)

    assert isinstance(ref, MediaRef)
    assert ref.mime == "image/png"
    assert ref.size == len(b"hello world")
    assert Path(ref.path).exists()
    assert Path(ref.path).read_bytes() == b"hello world"


@pytest.mark.unit
def test_store_bytes_is_content_addressed(tmp_path):
    ref1 = store_bytes(b"same content", "image/png", tmp_path)
    ref2 = store_bytes(b"same content", "image/png", tmp_path)

    assert ref1.hash == ref2.hash
    assert ref1.path == ref2.path


@pytest.mark.unit
def test_store_bytes_different_content_different_hash(tmp_path):
    ref1 = store_bytes(b"content A", "image/png", tmp_path)
    ref2 = store_bytes(b"content B", "image/png", tmp_path)

    assert ref1.hash != ref2.hash
    assert ref1.path != ref2.path


@pytest.mark.unit
def test_store_bytes_dedupes_regardless_of_declared_mime(tmp_path):
    """Same bytes must resolve to the same file even if mime differs — the
    hash, not the mime, is the identity. A path that forked per-mime would
    silently duplicate storage for the same content.
    """
    ref1 = store_bytes(b"identical payload", "image/png", tmp_path)
    ref2 = store_bytes(b"identical payload", "image/jpeg", tmp_path)

    assert ref1.hash == ref2.hash
    assert ref1.path == ref2.path
    # only one file actually exists on disk for this content
    assert sum(1 for _ in tmp_path.rglob("*") if _.is_file()) == 1


@pytest.mark.unit
def test_store_bytes_does_not_rewrite_existing_file(tmp_path):
    ref = store_bytes(b"payload", "image/png", tmp_path)
    path = Path(ref.path)
    original_mtime = path.stat().st_mtime_ns

    store_bytes(b"payload", "image/png", tmp_path)

    assert path.stat().st_mtime_ns == original_mtime


@pytest.mark.unit
def test_path_for_hash_shards_by_first_two_chars(tmp_path):
    hash_ = "abcdef1234567890"
    path = path_for_hash(tmp_path, hash_)

    assert path == tmp_path / "ab" / hash_

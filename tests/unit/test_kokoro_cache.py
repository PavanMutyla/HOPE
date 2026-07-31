"""Unit tests for core/voice/kokoro_cache.py — shared Kokoro model-cache helpers."""

import pytest

from core.voice.kokoro_cache import ensure_kokoro_files, recover_corrupted_kokoro_cache


@pytest.mark.unit
def test_ensure_kokoro_files_returns_model_and_voices_paths():
    model_file, voices_file = ensure_kokoro_files()
    assert model_file.name == "kokoro-v1.0.onnx"
    assert voices_file.name == "voices-v1.0.bin"


@pytest.mark.unit
def test_ensure_kokoro_files_returns_paths_in_same_directory():
    model_file, voices_file = ensure_kokoro_files()
    assert model_file.parent == voices_file.parent


@pytest.mark.unit
def test_recover_corrupted_kokoro_cache_deletes_existing_files(tmp_path):
    model_file = tmp_path / "kokoro-v1.0.onnx"
    voices_file = tmp_path / "voices-v1.0.bin"
    model_file.write_bytes(b"partial")
    voices_file.write_bytes(b"partial")

    recover_corrupted_kokoro_cache(model_file, voices_file)

    assert not model_file.exists()
    assert not voices_file.exists()


@pytest.mark.unit
def test_recover_corrupted_kokoro_cache_tolerates_missing_files(tmp_path):
    """missing_ok=True — must not raise if a file was already partially cleaned up."""
    model_file = tmp_path / "kokoro-v1.0.onnx"
    voices_file = tmp_path / "voices-v1.0.bin"

    recover_corrupted_kokoro_cache(model_file, voices_file)

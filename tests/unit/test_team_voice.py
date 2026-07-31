"""Unit tests for core/voice/team_voice.py — standalone TTS+audio-output channel.

Kokoro and pyaudio are both mocked so these run without a real model download
or real audio hardware.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

import core.voice.team_voice as team_voice_module
from core.voice.team_voice import TeamVoice


def _fake_kokoro(chunks):
    """A MagicMock kokoro_onnx.Kokoro whose create_stream() yields the given chunks."""
    kokoro = MagicMock()

    async def fake_stream(*args, **kwargs):
        for chunk in chunks:
            yield chunk

    kokoro.create_stream = MagicMock(side_effect=fake_stream)
    return kokoro


@pytest.fixture
def mock_kokoro_and_pyaudio(monkeypatch):
    """Patches Kokoro construction and pyaudio.PyAudio so TeamVoice never touches
    real files or real audio hardware. Returns (kokoro_instance, pyaudio_instance, stream)."""
    stream = MagicMock()
    pyaudio_instance = MagicMock()
    pyaudio_instance.get_format_from_width = MagicMock(return_value=8)
    pyaudio_instance.open = MagicMock(return_value=stream)

    monkeypatch.setattr(team_voice_module.pyaudio, "PyAudio", MagicMock(return_value=pyaudio_instance))
    monkeypatch.setattr(team_voice_module, "_build_kokoro_engine", lambda: MagicMock())

    return pyaudio_instance, stream


@pytest.mark.unit
async def test_speak_writes_synthesized_audio_to_own_stream(mock_kokoro_and_pyaudio, monkeypatch):
    _pyaudio_instance, stream = mock_kokoro_and_pyaudio
    samples = np.array([0.5, -0.5], dtype=np.float32)
    kokoro = _fake_kokoro([(samples, 24000)])
    monkeypatch.setattr(team_voice_module, "_build_kokoro_engine", lambda: kokoro)

    voice = TeamVoice(voice_id="af_bella")
    await voice.speak("hello team")

    expected_bytes = (samples * 32767).astype(np.int16).tobytes()
    stream.write.assert_called_once_with(expected_bytes)


@pytest.mark.unit
async def test_speak_passes_voice_language_and_speed_to_kokoro(mock_kokoro_and_pyaudio, monkeypatch):
    kokoro = _fake_kokoro([(np.array([0.0], dtype=np.float32), 24000)])
    monkeypatch.setattr(team_voice_module, "_build_kokoro_engine", lambda: kokoro)

    voice = TeamVoice(voice_id="af_bella", language="en-gb", speed=1.2)
    await voice.speak("hello")

    kokoro.create_stream.assert_called_once_with(
        "hello", voice="af_bella", lang="en-gb", speed=1.2
    )


@pytest.mark.unit
async def test_ensure_stream_opens_new_stream_on_first_chunk(mock_kokoro_and_pyaudio, monkeypatch):
    pyaudio_instance, _stream = mock_kokoro_and_pyaudio
    kokoro = _fake_kokoro([(np.array([0.0], dtype=np.float32), 24000)])
    monkeypatch.setattr(team_voice_module, "_build_kokoro_engine", lambda: kokoro)

    voice = TeamVoice(voice_id="af_bella")
    await voice.speak("hi")

    pyaudio_instance.open.assert_called_once()
    assert pyaudio_instance.open.call_args.kwargs["rate"] == 24000
    assert pyaudio_instance.open.call_args.kwargs["channels"] == 1


@pytest.mark.unit
async def test_ensure_stream_reuses_stream_for_same_sample_rate(mock_kokoro_and_pyaudio, monkeypatch):
    pyaudio_instance, _stream = mock_kokoro_and_pyaudio
    chunks = [
        (np.array([0.1], dtype=np.float32), 24000),
        (np.array([0.2], dtype=np.float32), 24000),
    ]
    kokoro = _fake_kokoro(chunks)
    monkeypatch.setattr(team_voice_module, "_build_kokoro_engine", lambda: kokoro)

    voice = TeamVoice(voice_id="af_bella")
    await voice.speak("hi there")

    pyaudio_instance.open.assert_called_once()


@pytest.mark.unit
async def test_ensure_stream_reopens_on_sample_rate_change(mock_kokoro_and_pyaudio, monkeypatch):
    pyaudio_instance, _stream = mock_kokoro_and_pyaudio
    chunks = [
        (np.array([0.1], dtype=np.float32), 24000),
        (np.array([0.2], dtype=np.float32), 16000),
    ]
    kokoro = _fake_kokoro(chunks)
    monkeypatch.setattr(team_voice_module, "_build_kokoro_engine", lambda: kokoro)

    voice = TeamVoice(voice_id="af_bella")
    await voice.speak("hi there")

    assert pyaudio_instance.open.call_count == 2


@pytest.mark.unit
def test_close_stops_and_closes_stream_and_terminates_pyaudio(mock_kokoro_and_pyaudio):
    pyaudio_instance, stream = mock_kokoro_and_pyaudio

    voice = TeamVoice(voice_id="af_bella")
    voice._stream = stream  # simulate a stream having been opened by a prior speak()

    voice.close()

    stream.stop_stream.assert_called_once()
    stream.close.assert_called_once()
    pyaudio_instance.terminate.assert_called_once()


@pytest.mark.unit
def test_close_tolerates_never_having_spoken(mock_kokoro_and_pyaudio):
    """close() must not blow up if speak() was never called (no stream was ever opened)."""
    voice = TeamVoice(voice_id="af_bella")
    voice.close()

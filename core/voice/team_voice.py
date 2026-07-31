import asyncio
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pyaudio
from kokoro_onnx import Kokoro

from core.voice.kokoro_cache import ensure_kokoro_files, recover_corrupted_kokoro_cache


def _build_kokoro_engine() -> Kokoro:
    """Construct a raw kokoro_onnx.Kokoro engine, recovering once from a corrupted cache."""
    model_file, voices_file = ensure_kokoro_files()
    try:
        return Kokoro(str(model_file), str(voices_file))
    except Exception:
        if not model_file.exists() and not voices_file.exists():
            raise
        recover_corrupted_kokoro_cache(model_file, voices_file)
        return Kokoro(str(model_file), str(voices_file))


class TeamVoice:
    """A standalone TTS + audio-output channel for one team-mode agent.

    Fully independent of the shared pipecat pipeline's TTS/transport — its own
    Kokoro engine, own PyAudio output stream, own executor. No pipecat Pipeline
    or PipelineWorker involved. Multiple TeamVoice instances (and HOPE's own
    pipeline TTS) can play concurrently: the OS audio server (PipeWire/
    PulseAudio) mixes independent output streams, confirmed empirically on
    this project's target machine before this class was written.
    """

    def __init__(self, voice_id: str, language: str = "en-us", speed: float = 1.0) -> None:
        self._voice_id = voice_id
        self._language = language
        self._speed = speed
        self._kokoro = _build_kokoro_engine()
        self._pyaudio = pyaudio.PyAudio()
        self._stream: pyaudio.Stream | None = None
        self._stream_sample_rate: int | None = None
        # Single thread: writes are strictly sequential per voice, same
        # reasoning pipecat's own LocalAudioOutputTransport uses.
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def speak(self, text: str) -> None:
        """Synthesize text and play it on this voice's own independent output stream."""
        loop = asyncio.get_event_loop()
        stream = self._kokoro.create_stream(
            text, voice=self._voice_id, lang=self._language, speed=self._speed
        )
        async for samples, sample_rate in stream:
            self._ensure_stream(sample_rate)
            audio_int16 = (samples * 32767).astype(np.int16).tobytes()
            await loop.run_in_executor(self._executor, self._stream.write, audio_int16)

    def _ensure_stream(self, sample_rate: int) -> None:
        if self._stream is not None and self._stream_sample_rate == sample_rate:
            return
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
        self._stream = self._pyaudio.open(
            format=self._pyaudio.get_format_from_width(2),
            channels=1,
            rate=sample_rate,
            output=True,
        )
        self._stream_sample_rate = sample_rate

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        self._pyaudio.terminate()
        self._executor.shutdown(wait=False)

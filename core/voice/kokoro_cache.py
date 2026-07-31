from pathlib import Path

from loguru import logger
from pipecat.services.kokoro.tts import KOKORO_CACHE_DIR


def ensure_kokoro_files() -> tuple[Path, Path]:
    """Locate Kokoro's model + voices cache files, logging on first-ever download.

    Doesn't download itself — construction of the Kokoro engine (whether via
    KokoroTTSService or the raw kokoro_onnx.Kokoro class) triggers that. Callers
    should construct, and on failure call recover_corrupted_kokoro_cache() below
    and retry once.
    """
    model_file = KOKORO_CACHE_DIR / "kokoro-v1.0.onnx"
    voices_file = KOKORO_CACHE_DIR / "voices-v1.0.bin"

    if not model_file.exists() or not voices_file.exists():
        logger.info("Kokoro TTS model not found locally — downloading (~300MB, one-time)...")

    return model_file, voices_file


def recover_corrupted_kokoro_cache(model_file: Path, voices_file: Path) -> None:
    """Delete a corrupted/partial Kokoro cache so the next construction re-downloads it.

    Kokoro only checks that cache files *exist*, not that they're valid — a
    truncated download (e.g. an interrupted transfer on first run on a new
    machine) leaves a file that exists but fails to load.
    """
    logger.warning(
        "Kokoro TTS model cache looks corrupted or incomplete — deleting and re-downloading..."
    )
    model_file.unlink(missing_ok=True)
    voices_file.unlink(missing_ok=True)

"""PromptEchoFilter — drops transcriptions that are only the STT prompt.

OpenAI's transcription models take a `prompt` to bias spelling and context
("Pavan is speaking..."). On silence or background noise they sometimes
return that prompt as the transcript, so the pipeline treated a sentence
Pavan never said as his turn: HOPE answered it, and it was stored in
episodic memory as something he said.

Placed directly after STT, so nothing downstream (team broadcast, status,
the live feed, the context aggregator) ever sees the echo. A transcript
that merely mentions the same words alongside real speech passes through.
"""

import re

from loguru import logger
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# Words the model sometimes wraps around the echo ("Context: Pavan is ...").
_MAX_EXTRA_WORDS = 2


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def is_prompt_echo(transcript: str, prompt: str) -> bool:
    said, echo = _words(transcript), _words(prompt)
    if not echo or len(said) > len(echo) + _MAX_EXTRA_WORDS:
        return False
    # The prompt's words, in order, as one contiguous run inside the transcript.
    return any(said[i:i + len(echo)] == echo for i in range(len(said) - len(echo) + 1))


class PromptEchoFilter(FrameProcessor):
    def __init__(self, prompt: str):
        super().__init__()
        self._prompt = prompt

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and is_prompt_echo(frame.text or "", self._prompt):
            logger.debug(f"Dropped a transcript that only echoed the STT prompt: {frame.text!r}")
            return
        await self.push_frame(frame, direction)

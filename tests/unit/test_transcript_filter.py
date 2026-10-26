"""PromptEchoFilter: the STT model sometimes returns its own prompt on
silence, and the pipeline used to treat that as something Pavan said."""

import pytest
from pipecat.frames.frames import TextFrame, TranscriptionFrame, UserStartedSpeakingFrame
from pipecat.processors.frame_processor import FrameDirection

from core.voice.pipeline import STT_PROMPT
from core.voice.transcript_filter import PromptEchoFilter, is_prompt_echo

pytestmark = pytest.mark.unit

# The prompt as it was when the echoes below were recorded (USER_NAME=Pavan).
RECORDED_PROMPT = "Pavan is speaking. Conversation about business, tech, and personal topics."


def transcription(text: str) -> TranscriptionFrame:
    return TranscriptionFrame(text=text, user_id="pavan", timestamp="2026-10-27T00:00:00Z")


@pytest.mark.parametrize("echo", [
    # both seen verbatim in episodic memory, stored as Pavan's turns
    "Pavan is speaking. Conversation about business, tech, and personal topics.",
    "Context: Pavan is speaking. Conversation about business, tech, and personal topics.",
    "pavan is speaking, conversation about business tech and personal topics",
])
def test_echoes_of_the_prompt_are_recognised(echo):
    assert is_prompt_echo(echo, RECORDED_PROMPT)


def test_the_prompt_carries_the_user_name_from_env():
    assert STT_PROMPT.startswith("TestUser is speaking.")


@pytest.mark.parametrize("speech", [
    "What is the latest Python version?",
    "Pavan is speaking.",  # only part of the prompt
    "Let's have a conversation about business, tech, and personal topics, "
    "starting with what Pavan is speaking about at the conference next week.",
    "",
])
def test_real_speech_is_not_mistaken_for_an_echo(speech):
    assert not is_prompt_echo(speech, RECORDED_PROMPT)


async def _run(*frames):
    f = PromptEchoFilter(STT_PROMPT)
    pushed = []

    async def capture(frame, direction=FrameDirection.DOWNSTREAM):
        pushed.append(frame)

    f.push_frame = capture
    for frame in frames:
        await f.process_frame(frame, FrameDirection.DOWNSTREAM)
    return pushed


async def test_the_echo_is_dropped_and_everything_else_passes_untouched():
    real = transcription("What is the latest Python version?")
    others = [UserStartedSpeakingFrame(), TextFrame("unrelated")]
    pushed = await _run(others[0], transcription(STT_PROMPT), real, others[1])
    assert pushed == [others[0], real, others[1]]

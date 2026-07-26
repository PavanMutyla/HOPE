"""Live end-to-end test of context summarization against the real OpenAI API.

Off by default — normal `pytest` runs stay offline and free. To run it:

    RUN_LIVE_TESTS=1 .venv/bin/pytest tests/integration/test_summarizer_live.py -v -s

Needs a real OPENAI_API_KEY in .env. Reads .env directly (via dotenv) so the
fake test env from conftest doesn't shadow the real key.
"""

import os

import pytest
from dotenv import dotenv_values
from openai import AsyncOpenAI

from core.voice.context_meter import ContextMeter
from core.voice.summarizer import ContextSummarizer

_env = dotenv_values(".env")
_key = _env.get("OPENAI_API_KEY", "")
_live = bool(os.getenv("RUN_LIVE_TESTS")) and _key.startswith("sk-")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _live, reason="set RUN_LIVE_TESTS=1 and a real OPENAI_API_KEY in .env"
    ),
]


class _Ctx:
    """Minimal stand-in for LLMContext: what ContextSummarizer touches."""

    def __init__(self, messages):
        self.messages = messages

    def set_messages(self, new):
        self.messages[:] = new


def _conversation():
    # planted, distinctive facts the summary should retain
    return [
        {"role": "system", "content": "You are HOPE, a helpful voice assistant."},
        {"role": "user", "content": "My name is Pavan and I run a company called Falconworks."},
        {"role": "assistant", "content": "Nice to meet you, Pavan."},
        {"role": "user", "content": "We ship the Orion release on March 3rd. Remind me to call the vendor, Acme Robotics."},
        {"role": "assistant", "content": "Got it — Orion ships March 3rd, and I'll note the Acme Robotics call."},
        {"role": "user", "content": "Also I'm allergic to peanuts, keep that in mind for restaurant picks."},
        {"role": "assistant", "content": "Noted: no peanuts."},
        {"role": "user", "content": "What's the weather like on Mars?"},
        {"role": "assistant", "content": "Cold and thin-aired — around minus 60 Celsius on average."},
    ]


@pytest.mark.asyncio
async def test_live_summarization_compresses_and_preserves_facts():
    from unittest.mock import MagicMock

    from settings import settings

    messages = _conversation()
    context = _Ctx(messages)
    meter = ContextMeter(context_limit=1000)  # 20% cap → max_tokens=200
    client = AsyncOpenAI(api_key=_key)

    summarizer = ContextSummarizer(
        context=context, meter=meter, panel=MagicMock(), client=client,
        episodic_memory=MagicMock(), session_id="live-test-session",
    )
    summarizer._keep_recent = 2

    original_len = len(messages)
    await summarizer._summarize()

    # 1. structure: system kept, head replaced by a developer summary, recent intact
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "developer"
    summary = messages[1]["content"]
    assert len(messages) < original_len, "should have fewer messages after compression"
    assert messages[-2:] == _conversation()[-2:], "recent turns must be preserved verbatim"

    # 2. the cap held: summary is far shorter than the 200-token ceiling would allow
    assert 0 < len(summary) < 4000

    # 3. content: the model actually retained the salient facts (lenient — any few)
    low = summary.lower()
    hits = sum(
        term in low
        for term in ["pavan", "falconworks", "orion", "march", "acme", "peanut"]
    )
    assert hits >= 3, f"summary lost too many facts: {summary!r}"
    print(f"\n--- live summary ({settings.summarizer_model}) ---\n{summary}\n")

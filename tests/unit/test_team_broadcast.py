"""Unit tests for core/voice/team_broadcast.py — TeamBroadcastObserver."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from core.voice.agent_state import agent_state
from core.voice.team_broadcast import PASS_TOKEN, TeamBroadcastObserver
from core.voice.team_registry import TeamMember, TeamRegistry
from core.voice.team_state import team_state
from core.voice.team_voice import TeamVoice


def _make_member(name: str) -> TeamMember:
    return TeamMember(
        name=name,
        interject_prompt=f"You are {name}, overhearing HOPE's conversation.",
        llm_model="gpt-4o-mini",
        voice=MagicMock(spec=TeamVoice),
    )


@pytest.fixture(autouse=True)
def reset_team_and_agent_state(monkeypatch):
    """Every test starts from a clean, deterministic team_state/agent_state
    regardless of what earlier tests in the session did."""
    monkeypatch.setattr(team_state, "enabled", False)
    monkeypatch.setattr(agent_state, "active", "hope")


# ─── _handle_frame gating ─────────────────────────────────────────

@pytest.mark.unit
def test_handle_frame_noop_when_team_mode_disabled():
    registry = TeamRegistry()
    registry.register(_make_member("atlas"))
    observer = TeamBroadcastObserver(registry, client=MagicMock())
    observer._maybe_interject = AsyncMock()

    observer._handle_frame(TranscriptionFrame(text="hi", user_id="pavan", timestamp=""))

    observer._maybe_interject.assert_not_called()


@pytest.mark.unit
def test_handle_frame_noop_for_non_transcription_frame(monkeypatch):
    monkeypatch.setattr(team_state, "enabled", True)
    registry = TeamRegistry()
    registry.register(_make_member("atlas"))
    observer = TeamBroadcastObserver(registry, client=MagicMock())
    observer._maybe_interject = AsyncMock()

    observer._handle_frame(Frame())

    observer._maybe_interject.assert_not_called()


@pytest.mark.unit
async def test_handle_frame_fires_interject_check_for_non_active_members(monkeypatch):
    monkeypatch.setattr(team_state, "enabled", True)
    atlas = _make_member("atlas")
    registry = TeamRegistry()
    registry.register(atlas)
    observer = TeamBroadcastObserver(registry, client=MagicMock())
    observer._maybe_interject = AsyncMock()

    observer._handle_frame(
        TranscriptionFrame(text="what's in my workspace", user_id="pavan", timestamp="")
    )
    await asyncio.sleep(0)

    observer._maybe_interject.assert_called_once_with(atlas, "what's in my workspace")


@pytest.mark.unit
async def test_handle_frame_skips_the_currently_active_agent(monkeypatch):
    monkeypatch.setattr(team_state, "enabled", True)
    monkeypatch.setattr(agent_state, "active", "atlas")
    registry = TeamRegistry()
    registry.register(_make_member("atlas"))
    observer = TeamBroadcastObserver(registry, client=MagicMock())
    observer._maybe_interject = AsyncMock()

    observer._handle_frame(TranscriptionFrame(text="hello", user_id="pavan", timestamp=""))
    await asyncio.sleep(0)

    observer._maybe_interject.assert_not_called()


@pytest.mark.unit
async def test_handle_frame_fires_for_every_non_active_member(monkeypatch):
    monkeypatch.setattr(team_state, "enabled", True)
    registry = TeamRegistry()
    registry.register(_make_member("atlas"))
    registry.register(_make_member("scout"))
    observer = TeamBroadcastObserver(registry, client=MagicMock())
    observer._maybe_interject = AsyncMock()

    observer._handle_frame(TranscriptionFrame(text="hi", user_id="pavan", timestamp=""))
    await asyncio.sleep(0)

    assert observer._maybe_interject.call_count == 2


# ─── process_frame pass-through contract ──────────────────────────

@pytest.mark.unit
async def test_process_frame_always_pushes_frame_through_unchanged():
    registry = TeamRegistry()
    observer = TeamBroadcastObserver(registry, client=MagicMock())
    observer.push_frame = AsyncMock()
    frame = TranscriptionFrame(text="hi", user_id="pavan", timestamp="")

    await observer.process_frame(frame, FrameDirection.DOWNSTREAM)

    observer.push_frame.assert_called_once_with(frame, FrameDirection.DOWNSTREAM)


# ─── _maybe_interject gate logic ──────────────────────────────────

def _mock_client(reply_text: str) -> MagicMock:
    client = MagicMock()
    completion = MagicMock()
    completion.choices[0].message.content = reply_text
    client.chat.completions.create = AsyncMock(return_value=completion)
    return client


@pytest.mark.unit
async def test_maybe_interject_speaks_when_reply_is_not_pass():
    atlas = _make_member("atlas")
    client = _mock_client("Careful, that file is read-only.")
    observer = TeamBroadcastObserver(TeamRegistry(), client=client)

    await observer._maybe_interject(atlas, "I'm about to overwrite config.json")

    atlas.voice.speak.assert_called_once_with("Careful, that file is read-only.")


@pytest.mark.unit
async def test_maybe_interject_does_not_speak_on_pass():
    atlas = _make_member("atlas")
    client = _mock_client(PASS_TOKEN)
    observer = TeamBroadcastObserver(TeamRegistry(), client=client)

    await observer._maybe_interject(atlas, "what's the weather like")

    atlas.voice.speak.assert_not_called()


@pytest.mark.unit
async def test_maybe_interject_treats_pass_case_insensitively():
    atlas = _make_member("atlas")
    client = _mock_client("  pass  ")
    observer = TeamBroadcastObserver(TeamRegistry(), client=client)

    await observer._maybe_interject(atlas, "unrelated small talk")

    atlas.voice.speak.assert_not_called()


@pytest.mark.unit
async def test_maybe_interject_sends_member_prompt_and_transcript():
    atlas = _make_member("atlas")
    client = _mock_client(PASS_TOKEN)
    observer = TeamBroadcastObserver(TeamRegistry(), client=client)

    await observer._maybe_interject(atlas, "the transcript text")

    call_kwargs = client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert call_kwargs["messages"][0]["content"] == atlas.interject_prompt
    assert call_kwargs["messages"][1]["content"] == "the transcript text"


@pytest.mark.unit
async def test_maybe_interject_swallows_client_errors():
    """A failed background gate check must not raise into the caller (fire-and-forget)."""
    atlas = _make_member("atlas")
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=RuntimeError("network down"))
    observer = TeamBroadcastObserver(TeamRegistry(), client=client)

    await observer._maybe_interject(atlas, "hello")

    atlas.voice.speak.assert_not_called()


@pytest.mark.unit
async def test_maybe_interject_does_not_speak_on_empty_reply():
    atlas = _make_member("atlas")
    client = _mock_client("")
    observer = TeamBroadcastObserver(TeamRegistry(), client=client)

    await observer._maybe_interject(atlas, "hello")

    atlas.voice.speak.assert_not_called()

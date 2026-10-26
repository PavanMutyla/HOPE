"""Unit tests for the live session feed — memory/live/ (SQLite layer + facade)
and core/voice/live_feed.py's LiveUserTap + LiveFeedObserver.

This is the only channel out of the running pipeline into the dashboard
process, so two properties matter most and are pinned hardest here:

1. **A write failure must never disturb the pipeline.** Every observer write is
   wrapped best-effort. A stale dashboard is a small problem; a stalled audio
   pipeline is the product breaking.
2. **Frames must pass through untouched.** The observer is a sidecar. If it
   swallowed or reordered a frame, audio would break in a way that looks
   nothing like a dashboard bug.
"""

from unittest.mock import MagicMock

import pytest

from pipecat.frames.frames import (
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TextFrame,
    TranscriptionFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    UserStartedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from core.voice.live_feed import LiveFeedObserver, LiveUserTap
from memory.live import live
from memory.live.store import LiveFeed

pytestmark = pytest.mark.unit


@pytest.fixture
def feed(tmp_path):
    f = LiveFeed(db_path=tmp_path / "live.db")
    yield f
    f.close()


def transcription(text: str) -> TranscriptionFrame:
    return TranscriptionFrame(text=text, user_id="pavan", timestamp="2026-09-05T00:00:00Z")


async def observe(observer, *frames):
    for frame in frames:
        await observer.process_frame(frame, FrameDirection.DOWNSTREAM)


# ─── store layer ────────────────────────────────────────────────

def test_unwritten_feed_reads_as_idle(feed):
    """The dashboard renders 'not running' off this, so it must never be None
    — hope.py may simply not have started yet."""
    status = feed.get_status()
    assert status.state == "idle"
    assert status.session_id == ""


def test_start_session_sets_listening_and_identity(feed):
    feed.start_session("run-1", "hope")

    status = feed.get_status()
    assert status.state == "listening"
    assert status.session_id == "run-1"
    assert status.agent == "hope"
    assert status.started_at != ""


def test_start_session_clears_the_previous_run(feed):
    """Otherwise last night's conversation renders as though it were live."""
    feed.start_session("run-1", "hope")
    feed.append_turn("run-1", "user", "", "yesterday's question")

    feed.start_session("run-2", "hope")

    assert feed.get_turns("run-1") == []
    assert feed.get_turns("run-2") == []


def test_start_session_resets_stale_state(feed):
    feed.start_session("run-1", "hope")
    feed.set_context_pct(0.87)
    feed.set_last_tool("get_tasks")

    feed.start_session("run-2", "hope")

    status = feed.get_status()
    assert status.context_pct == 0.0
    assert status.last_tool == ""


def test_end_session_goes_idle_but_keeps_the_transcript(feed):
    """A panel that blanks the instant HOPE exits looks broken; the last
    conversation should stay readable until the next run replaces it."""
    feed.start_session("run-1", "hope")
    feed.append_turn("run-1", "user", "", "what's on today?")

    feed.end_session()

    assert feed.get_status().state == "idle"
    assert len(feed.get_turns("run-1")) == 1


def test_turns_are_returned_oldest_first(feed):
    feed.start_session("run-1", "hope")
    for text in ["first", "second", "third"]:
        feed.append_turn("run-1", "user", "", text)

    assert [t.text for t in feed.get_turns("run-1")] == ["first", "second", "third"]


def test_seq_is_assigned_by_the_store_not_the_caller(feed):
    feed.start_session("run-1", "hope")

    assert feed.append_turn("run-1", "user", "", "a") == 0
    assert feed.append_turn("run-1", "assistant", "hope", "b") == 1
    assert feed.append_turn("run-1", "user", "", "c") == 2


def test_get_turns_limit_keeps_the_most_recent_in_order(feed):
    """The limit trims from the *start* — a long session should show its tail,
    still oldest-first for rendering."""
    feed.start_session("run-1", "hope")
    for i in range(10):
        feed.append_turn("run-1", "user", "", f"turn {i}")

    turns = feed.get_turns("run-1", limit=3)
    assert [t.text for t in turns] == ["turn 7", "turn 8", "turn 9"]


def test_turns_are_scoped_to_their_session(feed):
    feed.start_session("run-1", "hope")
    feed.append_turn("run-1", "user", "", "mine")
    feed.append_turn("other-run", "user", "", "theirs")

    assert [t.text for t in feed.get_turns("run-1")] == ["mine"]


def test_state_and_agent_updates_land(feed):
    feed.start_session("run-1", "hope")
    feed.set_state("speaking")
    feed.set_agent("atlas")
    feed.set_context_pct(0.42)
    feed.set_last_tool("get_weather")

    status = feed.get_status()
    assert (status.state, status.agent) == ("speaking", "atlas")
    assert status.context_pct == 0.42
    assert status.last_tool == "get_weather"


def test_connection_is_usable_across_processes_style_reopen(tmp_path):
    """The dashboard opens its own connection to the same file — a second
    LiveFeed must see what the first wrote."""
    writer = LiveFeed(db_path=tmp_path / "live.db")
    writer.start_session("run-1", "hope")
    writer.append_turn("run-1", "user", "", "written by the pipeline")

    reader = LiveFeed(db_path=tmp_path / "live.db")
    assert [t.text for t in reader.get_turns("run-1")] == ["written by the pipeline"]
    assert reader.get_status().session_id == "run-1"

    writer.close()
    reader.close()


def test_wal_and_busy_timeout_are_set(tmp_path):
    """Both processes write/read concurrently; without WAL this deadlocks under
    load rather than failing visibly."""
    conn = live.connect(tmp_path / "live.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    conn.close()


# ─── observer ───────────────────────────────────────────────────

async def test_user_speech_becomes_a_user_turn(feed):
    feed.start_session("run-1", "hope")
    observer = LiveUserTap(feed, "run-1")

    await observe(observer, transcription("what's on my board today?"))

    turns = feed.get_turns("run-1")
    assert len(turns) == 1
    assert (turns[0].role, turns[0].text) == ("user", "what's on my board today?")


async def test_streamed_reply_is_written_as_one_turn(feed):
    """The whole reason this observer exists: assistant text is never logged
    anywhere, it only arrives as a stream of LLMTextFrames."""
    feed.start_session("run-1", "hope")
    observer = LiveFeedObserver(feed, "run-1")

    await observe(
        observer,
        LLMFullResponseStartFrame(),
        LLMTextFrame("Three things "),
        LLMTextFrame("on the board "),
        LLMTextFrame("today."),
        LLMFullResponseEndFrame(),
    )

    turns = feed.get_turns("run-1")
    assert len(turns) == 1
    assert turns[0].role == "assistant"
    assert turns[0].text == "Three things on the board today."


async def test_a_tool_call_turn_writes_no_empty_bubble(feed):
    """A turn that only calls a tool produces no text — writing it would render
    as HOPE saying nothing."""
    feed.start_session("run-1", "hope")
    observer = LiveFeedObserver(feed, "run-1")

    await observe(observer, LLMFullResponseStartFrame(), LLMFullResponseEndFrame())

    assert feed.get_turns("run-1") == []


async def test_reply_buffer_does_not_leak_between_turns(feed):
    feed.start_session("run-1", "hope")
    observer = LiveFeedObserver(feed, "run-1")

    await observe(
        observer,
        LLMFullResponseStartFrame(), LLMTextFrame("first reply"), LLMFullResponseEndFrame(),
        LLMFullResponseStartFrame(), LLMTextFrame("second reply"), LLMFullResponseEndFrame(),
    )

    assert [t.text for t in feed.get_turns("run-1")] == ["first reply", "second reply"]


async def test_blank_transcription_is_ignored(feed):
    """VAD sometimes fires on silence; an empty bubble is worse than nothing."""
    feed.start_session("run-1", "hope")
    observer = LiveUserTap(feed, "run-1")

    await observe(observer, transcription("   "))

    assert feed.get_turns("run-1") == []


async def test_state_tracks_the_conversation(feed):
    feed.start_session("run-1", "hope")
    tap = LiveUserTap(feed, "run-1")
    observer = LiveFeedObserver(feed, "run-1")

    await observe(tap, UserStartedSpeakingFrame())
    assert feed.get_status().state == "listening"

    await observe(observer, LLMFullResponseStartFrame())
    assert feed.get_status().state == "thinking"

    await observe(observer, TTSStartedFrame())
    assert feed.get_status().state == "speaking"

    await observe(observer, TTSStoppedFrame())
    assert feed.get_status().state == "listening"


async def test_context_pct_is_read_from_the_meter(feed):
    feed.start_session("run-1", "hope")
    meter = MagicMock()
    meter.context_pct = 0.63
    observer = LiveFeedObserver(feed, "run-1", meter)

    await observe(
        observer, LLMFullResponseStartFrame(), LLMTextFrame("hi"), LLMFullResponseEndFrame()
    )

    assert feed.get_status().context_pct == 0.63


@pytest.mark.parametrize("cls", [LiveUserTap, LiveFeedObserver])
async def test_every_frame_passes_through_untouched(feed, cls):
    """It's a sidecar. Dropping or altering a frame here would break audio in a
    way that looks nothing like a dashboard bug."""
    feed.start_session("run-1", "hope")
    observer = cls(feed, "run-1")
    pushed = []

    async def capture(frame, direction):
        pushed.append(frame)

    observer.push_frame = capture

    frames = [
        UserStartedSpeakingFrame(),
        transcription("hello"),
        LLMFullResponseStartFrame(),
        LLMTextFrame("hi"),
        LLMFullResponseEndFrame(),
        TextFrame("unrelated"),
        TTSStartedFrame(),
        TTSStoppedFrame(),
    ]
    await observe(observer, *frames)

    assert pushed == frames


@pytest.mark.parametrize("cls", [LiveUserTap, LiveFeedObserver])
async def test_a_dead_feed_never_breaks_the_pipeline(feed, cls):
    """The contract that matters most: the dashboard failing must cost nothing
    but the dashboard."""
    feed.start_session("run-1", "hope")
    observer = cls(feed, "run-1")
    feed.close()  # every subsequent write raises ProgrammingError

    pushed = []

    async def capture(frame, direction):
        pushed.append(frame)

    observer.push_frame = capture

    await observe(
        observer,
        transcription("still has to get through"),
        LLMFullResponseStartFrame(),
        LLMTextFrame("and so does this"),
        LLMFullResponseEndFrame(),
    )

    assert len(pushed) == 4


# ─── liveness ───────────────────────────────────────────────────

def test_heartbeat_touches_updated_at_and_nothing_else(feed):
    feed.start_session("run-1", "hope")
    feed.set_state("speaking")
    before = feed.get_status()

    feed.heartbeat()

    after = feed.get_status()
    assert after.updated_at >= before.updated_at
    assert after.state == "speaking"
    assert after.session_id == "run-1"


async def test_each_turn_is_written_once_by_exactly_one_writer(feed):
    """User turns are the tap's, replies are the observer's. Both seeing the
    same frame stream must still produce one row per turn."""
    feed.start_session("run-1", "hope")
    tap, observer = LiveUserTap(feed, "run-1"), LiveFeedObserver(feed, "run-1")
    frames = [
        transcription("hello"),
        LLMFullResponseStartFrame(), LLMTextFrame("hi Pavan"), LLMFullResponseEndFrame(),
    ]
    await observe(tap, *frames)
    await observe(observer, *frames)

    assert [(t.role, t.text) for t in feed.get_turns("run-1")] == [
        ("user", "hello"), ("assistant", "hi Pavan"),
    ]


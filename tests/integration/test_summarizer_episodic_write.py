"""Closes the loop the rest of the suite leaves open: a real ContextSummarizer
driving a real EpisodicMemory against a real SQLite file, across a real thread
boundary.

Why this file exists as its own thing:

- `tests/unit/test_summarizer.py` mocks `episodic_memory`, so it proves the
  summarizer *calls* write(), not that the write lands.
- `tests/integration/test_episodic_memory_pipeline.py` drives EpisodicMemory
  directly on the main thread, so it proves the store works, not that the
  summarizer's call path reaches it.
- `tests/integration/test_summarizer_live.py` passes `episodic_memory=MagicMock()`
  and is off by default anyway.

Nothing joined the two halves. That mattered because `_write_episodic` /
`flush()` offload through `asyncio.to_thread` and swallow every exception
(`except Exception: logger.exception(...)`) — exactly the shape that once hid
a sqlite "objects created in a thread can only be used in that same thread"
error and silently dropped *every* real fold's episodic write. A regression
there is invisible in logs nobody reads and invisible to every existing test.

The load-bearing detail in these tests: EpisodicMemory is constructed on the
main thread and written from a worker thread, matching production
(`build_pipeline()` constructs it, the fold task writes it). Constructing it
inside the worker thread would pass even with the bug reintroduced.
"""

import threading
from unittest.mock import AsyncMock, MagicMock

import pytest

chromadb = pytest.importorskip("chromadb")

from core.voice.context_meter import ContextMeter  # noqa: E402
from core.voice.summarizer import UNSUMMARIZED_MARKER, ContextSummarizer  # noqa: E402
from memory.episodic_memory import episodic  # noqa: E402
from memory.episodic_memory.store import EpisodicMemory  # noqa: E402

SUMMARY_TEXT = "Pavan ships Orion on March 3rd and is allergic to peanuts."


class _Ctx:
    """Minimal stand-in for LLMContext — only what ContextSummarizer touches."""

    def __init__(self, messages):
        self.messages = messages

    def set_messages(self, new):
        self.messages[:] = new


def _conversation() -> list[dict]:
    return [
        {"role": "system", "content": "You are HOPE."},
        {"role": "user", "content": "My name is Pavan."},
        {"role": "assistant", "content": "Hello, Pavan."},
        {"role": "user", "content": "Orion ships March 3rd."},
        {"role": "assistant", "content": "Noted."},
        {"role": "user", "content": "I'm allergic to peanuts."},
        {"role": "assistant", "content": "No peanuts."},
    ]


@pytest.fixture
def memory(tmp_path, fake_embedding_function):
    """Built on the main thread, on purpose — see module docstring."""
    store = EpisodicMemory(
        db_path=tmp_path / "episodic.db",
        media_dir=tmp_path / "media",
        persist_dir=tmp_path / "chroma",
        embedding_function=fake_embedding_function,
    )
    yield store
    store.close()


def _summarizer(context, memory, *, session_id="test-session"):
    client = AsyncMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=SUMMARY_TEXT))]
    )
    s = ContextSummarizer(
        context=context,
        meter=ContextMeter(context_limit=10000),
        panel=MagicMock(),
        client=client,
        episodic_memory=memory,
        session_id=session_id,
        semantic_memory=MagicMock(),
    )
    s._keep_recent = 2
    return s


@pytest.mark.integration
async def test_threshold_fold_persists_a_real_row(memory):
    """The fold path end to end: summarize -> to_thread -> sqlite + chroma."""
    context = _Ctx(_conversation())
    summarizer = _summarizer(context, memory)

    await summarizer._summarize()

    episodes = memory.list_by_reason("threshold")
    assert len(episodes) == 1, (
        "no 'threshold' episode landed — _write_episodic swallowed its exception"
    )
    episode = episodes[0]
    assert episode.summary == SUMMARY_TEXT
    assert episode.agent == "hope"
    assert episode.session_id == "test-session"
    # head = everything between the system message and the last 2 turns
    assert episode.span_turns == 4


@pytest.mark.integration
async def test_folded_episode_is_retrievable_through_the_vector_index(memory):
    """A row in SQLite that Chroma never indexed is unreachable by recall_memory,
    so the write is only really done once query() can find it again."""
    summarizer = _summarizer(_Ctx(_conversation()), memory)

    await summarizer._summarize()

    hits = memory.query("Orion peanuts Pavan", k=5, agent="hope")
    assert [e.summary for e in hits] == [SUMMARY_TEXT]


@pytest.mark.integration
async def test_flush_persists_a_real_session_end_raw_row(memory):
    """flush() has the same to_thread + swallow-everything shape as the fold
    path, and runs on the shutdown path where nobody is watching logs."""
    context = _Ctx(_conversation())
    summarizer = _summarizer(context, memory, session_id="flush-session")

    await summarizer.flush()

    episodes = memory.list_by_reason("session_end_raw")
    assert len(episodes) == 1, (
        "no 'session_end_raw' episode landed — flush() swallowed its exception"
    )
    episode = episodes[0]
    assert episode.summary.startswith(UNSUMMARIZED_MARKER)
    assert "allergic to peanuts" in episode.summary
    assert episode.session_id == "flush-session"


@pytest.mark.integration
async def test_fold_then_flush_share_one_session_id(memory):
    """Both write points are handed the same session_id in production
    (pipeline.py threads one uuid4 per process run through the summarizer);
    a fold and a shutdown flush in one run must be groupable as one session."""
    context = _Ctx(_conversation())
    summarizer = _summarizer(context, memory, session_id="one-run")

    await summarizer._summarize()
    await summarizer.flush()

    session_ids = {
        e.session_id
        for reason in ("threshold", "session_end_raw")
        for e in memory.list_by_reason(reason)
    }
    assert session_ids == {"one-run"}


@pytest.mark.integration
def test_connection_built_on_one_thread_is_writable_from_another(tmp_path):
    """The narrowest possible regression test for the original bug, with no
    summarizer in the way: sqlite3.connect() defaults to check_same_thread=True,
    which would raise ProgrammingError here. episodic.connect() must not."""
    conn = episodic.connect(tmp_path / "episodic.db")
    errors: list[Exception] = []

    def write_from_worker():
        try:
            episodic.create_episode(
                conn,
                tmp_path / "media",
                "hope",
                "cross-thread-session",
                "threshold",
                1,
                "written from a worker thread",
                [{"role": "user", "content": "hi"}],
            )
        except Exception as exc:  # noqa: BLE001 — recorded, then re-raised below
            errors.append(exc)

    worker = threading.Thread(target=write_from_worker)
    worker.start()
    worker.join()

    assert not errors, f"cross-thread write rejected: {errors[0]!r}"
    rows = episodic.list_episodes_by_reason(conn, "threshold")
    assert len(rows) == 1
    conn.close()


@pytest.mark.integration
async def test_write_failure_is_swallowed_and_does_not_break_the_fold(memory):
    """The flip side: the swallow is deliberate — a dead episodic store must
    never cost Pavan the live conversation. Pins that contract so nobody
    'fixes' it into a crash that drops the fold along with the write."""
    context = _Ctx(_conversation())
    summarizer = _summarizer(context, memory)
    memory.close()  # every subsequent write raises ProgrammingError

    await summarizer._summarize()  # must not raise

    # the context was still folded even though persistence failed
    assert context.messages[1]["role"] == "developer"
    assert SUMMARY_TEXT in context.messages[1]["content"]


@pytest.mark.integration
async def test_fold_write_actually_crosses_a_thread_boundary(memory, monkeypatch):
    """Guards the mechanism itself: if someone drops the asyncio.to_thread
    offload and calls write() inline, these blocking sqlite/chroma calls move
    onto the event loop and stall the audio pipeline. Nothing else notices."""
    main_thread = threading.get_ident()
    seen: list[int] = []
    real_write = memory.write

    def recording_write(*args, **kwargs):
        seen.append(threading.get_ident())
        return real_write(*args, **kwargs)

    monkeypatch.setattr(memory, "write", recording_write)

    await _summarizer(_Ctx(_conversation()), memory)._summarize()

    assert seen, "write() was never called"
    assert main_thread not in seen, "episodic write ran on the event loop thread"


# ── who owns a session, and what gets summarized ────────────────

WARM_START = {
    "role": "developer",
    "content": "Summary of your most recent session with Pavan (for context — don't "
               "repeat it verbatim): Pavan activated team mode and tried to contact Suresh.",
}
GREETING = {"role": "developer", "content": "Say a short hello to Pavan."}


@pytest.mark.integration
@pytest.mark.parametrize("active", ["atlas", "sarah"])
async def test_session_is_saved_under_hope_whoever_was_talking_at_the_end(memory, active):
    """The Python session was filed under "atlas" because Pavan was connected
    to Atlas when he quit, which hid it from HOPE's recall and warm start."""
    from core.voice.agent_state import agent_state

    agent_state.active = active
    try:
        summarizer = _summarizer(_Ctx(_conversation()), memory)
        await summarizer._summarize()
        await summarizer.flush()
    finally:
        agent_state.active = "hope"

    agents = {e.agent for r in ("threshold", "session_end_raw") for e in memory.list_by_reason(r)}
    assert agents == {"hope"}


@pytest.mark.integration
async def test_a_run_where_pavan_never_spoke_is_not_saved(memory):
    """HOPE's hello and nothing else must not become "the latest session"."""
    context = _Ctx([
        {"role": "system", "content": "You are HOPE."},
        WARM_START,
        GREETING,
        {"role": "assistant", "content": "Hey Pavan, what's on your mind today?"},
    ])
    await _summarizer(context, memory).flush()
    assert memory.list_by_reason("session_end_raw") == []


@pytest.mark.integration
async def test_upgrade_never_shows_the_summarizer_last_sessions_recap(memory):
    """The session-end summary is written at the next startup from the raw
    rows; the warm-start recap stored among them must not reach the LLM, or
    it gets copied into this session's summary and on into every next one."""
    from core.voice.summarizer import upgrade_pending_episodes

    context = _Ctx([
        {"role": "system", "content": "You are HOPE."},
        WARM_START,
        GREETING,
        {"role": "assistant", "content": "Hey Pavan."},
        {"role": "user", "content": "What is the latest Python version?"},
        {"role": "assistant", "content": "Python 3.15."},
    ])
    await _summarizer(context, memory).flush()

    client = AsyncMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Pavan asked about Python 3.15."))]
    )
    await upgrade_pending_episodes(memory, client, MagicMock())

    transcript = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "latest Python version" in transcript
    assert "Suresh" not in transcript and "short hello" not in transcript
    (episode,) = memory.list_by_reason("session_end")
    assert (episode.agent, episode.summary) == ("hope", "Pavan asked about Python 3.15.")

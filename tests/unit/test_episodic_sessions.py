"""Unit tests for the session read path — `list_sessions()` and
`get_session_transcript()`, which back the dashboard's thread list and
transcript view.

These are the first read functions that treat `session_id` as a first-class
grouping rather than an opaque tag. There is no `sessions` table: a session is
whatever shares a session_id, computed on read (see schema.Session). That makes
the grouping and ordering logic the thing worth testing — a wrong GROUP BY
silently merges two conversations into one thread.
"""

import pytest

from memory.episodic_memory import episodic
from memory.episodic_memory.schema import Session

pytestmark = pytest.mark.unit


@pytest.fixture
def conn(tmp_path):
    c = episodic.connect(tmp_path / "episodic.db")
    yield c
    c.close()


def write(conn, tmp_path, *, session_id, agent="hope", reason="threshold",
          summary="s", messages=None, ts=None):
    return episodic.create_episode(
        conn, tmp_path / "media", agent, session_id, reason,
        len(messages or []), summary, messages or [], ts=ts,
    )


def turns(*texts):
    """Alternating user/assistant messages."""
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": text}
        for i, text in enumerate(texts)
    ]


# ─── list_sessions ──────────────────────────────────────────────

def test_no_sessions_when_nothing_written(conn):
    assert episodic.list_sessions(conn) == []


def test_one_episode_becomes_one_session(conn, tmp_path):
    write(conn, tmp_path, session_id="s1", summary="talked about Orion",
          messages=turns("hi", "hello"), ts="2026-08-16T19:00:00+00:00")

    sessions = episodic.list_sessions(conn)

    assert len(sessions) == 1
    assert isinstance(sessions[0], Session)
    assert sessions[0].session_id == "s1"
    assert sessions[0].episode_count == 1
    assert sessions[0].message_count == 2
    assert sessions[0].summary == "talked about Orion"


def test_several_folds_of_one_conversation_collapse_into_one_session(conn, tmp_path):
    """The dashboard shows conversations, not folds — a long session that
    summarized three times is still one thread in the sidebar."""
    for i, ts in enumerate(["19:00", "19:10", "19:20"]):
        write(conn, tmp_path, session_id="s1", summary=f"fold {i}",
              messages=turns("a", "b"), ts=f"2026-08-16T{ts}:00+00:00")

    sessions = episodic.list_sessions(conn)

    assert len(sessions) == 1
    assert sessions[0].episode_count == 3
    assert sessions[0].message_count == 6


def test_session_summary_comes_from_the_latest_fold(conn, tmp_path):
    """Where the conversation *ended up*, not where it started — the last fold
    (or the session_end summary that replaces it) is the useful one."""
    write(conn, tmp_path, session_id="s1", summary="early on",
          ts="2026-08-16T19:00:00+00:00")
    write(conn, tmp_path, session_id="s1", summary="how it ended",
          reason="session_end", ts="2026-08-16T19:30:00+00:00")

    assert episodic.list_sessions(conn)[0].summary == "how it ended"


def test_session_spans_first_to_last_episode(conn, tmp_path):
    write(conn, tmp_path, session_id="s1", ts="2026-08-16T19:00:00+00:00")
    write(conn, tmp_path, session_id="s1", ts="2026-08-16T19:45:00+00:00")

    session = episodic.list_sessions(conn)[0]
    assert session.started_at == "2026-08-16T19:00:00+00:00"
    assert session.ended_at == "2026-08-16T19:45:00+00:00"


def test_sessions_are_newest_first(conn, tmp_path):
    write(conn, tmp_path, session_id="old", ts="2026-07-01T10:00:00+00:00")
    write(conn, tmp_path, session_id="new", ts="2026-08-16T10:00:00+00:00")
    write(conn, tmp_path, session_id="middle", ts="2026-08-01T10:00:00+00:00")

    assert [s.session_id for s in episodic.list_sessions(conn)] == ["new", "middle", "old"]


def test_sessions_sort_by_last_activity_not_first(conn, tmp_path):
    """A conversation started earlier but continued later belongs at the top."""
    write(conn, tmp_path, session_id="started_first", ts="2026-08-01T10:00:00+00:00")
    write(conn, tmp_path, session_id="started_later", ts="2026-08-02T10:00:00+00:00")
    write(conn, tmp_path, session_id="started_first", ts="2026-08-03T10:00:00+00:00")

    assert episodic.list_sessions(conn)[0].session_id == "started_first"


def test_two_agents_under_one_session_id_stay_separate_threads(conn, tmp_path):
    """Can't happen today (Atlas mints its own id per task) but the grouping
    must not silently interleave two agents' turns into one transcript."""
    write(conn, tmp_path, session_id="shared", agent="hope", messages=turns("a", "b"))
    write(conn, tmp_path, session_id="shared", agent="atlas", messages=turns("c", "d"))

    sessions = episodic.list_sessions(conn)
    assert len(sessions) == 2
    assert {s.agent for s in sessions} == {"hope", "atlas"}
    assert all(s.message_count == 2 for s in sessions)


def test_list_sessions_filters_by_agent(conn, tmp_path):
    write(conn, tmp_path, session_id="h1", agent="hope")
    write(conn, tmp_path, session_id="a1", agent="atlas")

    assert [s.session_id for s in episodic.list_sessions(conn, agent="atlas")] == ["a1"]


def test_message_count_ignores_other_sessions(conn, tmp_path):
    """The count is a correlated subquery, which is exactly the shape that
    silently over-counts if its WHERE clause drifts."""
    write(conn, tmp_path, session_id="s1", messages=turns("a", "b"))
    write(conn, tmp_path, session_id="s2", messages=turns("c", "d", "e", "f"))

    by_id = {s.session_id: s for s in episodic.list_sessions(conn)}
    assert by_id["s1"].message_count == 2
    assert by_id["s2"].message_count == 4


def test_episode_with_no_messages_still_lists(conn, tmp_path):
    """Blackboard task_complete episodes carry `messages=[]` — they must not
    vanish from, or break, the listing."""
    write(conn, tmp_path, session_id="task-1", reason="task_complete",
          summary="Task: tidy downloads\nStatus: completed", messages=[])

    session = episodic.list_sessions(conn)[0]
    assert session.message_count == 0
    assert session.episode_count == 1


# ─── get_episode_ids_by_session ─────────────────────────────────

def test_episode_ids_come_back_oldest_first(conn, tmp_path):
    """Transcript order depends on this — the flattening in
    EpisodicMemory.get_session_transcript() walks these in the order given."""
    second = write(conn, tmp_path, session_id="s1", ts="2026-08-16T19:10:00+00:00")
    first = write(conn, tmp_path, session_id="s1", ts="2026-08-16T19:00:00+00:00")
    third = write(conn, tmp_path, session_id="s1", ts="2026-08-16T19:20:00+00:00")

    assert episodic.get_episode_ids_by_session(conn, "s1") == [first, second, third]


def test_episode_ids_exclude_other_sessions(conn, tmp_path):
    mine = write(conn, tmp_path, session_id="s1")
    write(conn, tmp_path, session_id="s2")

    assert episodic.get_episode_ids_by_session(conn, "s1") == [mine]


def test_unknown_session_returns_empty(conn):
    assert episodic.get_episode_ids_by_session(conn, "never-existed") == []

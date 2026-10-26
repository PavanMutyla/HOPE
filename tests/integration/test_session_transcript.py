"""EpisodicMemory.get_session_transcript() against a real store.

The flattening it does is the load-bearing part: a long conversation folds
several times, so its turns live across several episodes, and `seq` only orders
messages *within* one episode. Reassembling one continuous transcript therefore
depends on walking episodes in ts order and each one's messages in seq order.
Get that wrong and the dashboard renders a conversation out of sequence — which
looks like a data-corruption bug rather than an ordering one.
"""

import pytest

chromadb = pytest.importorskip("chromadb")

from memory.episodic_memory.store import EpisodicMemory  # noqa: E402


@pytest.fixture
def memory(tmp_path, fake_embedding_function):
    store = EpisodicMemory(
        db_path=tmp_path / "episodic.db",
        media_dir=tmp_path / "media",
        persist_dir=tmp_path / "chroma",
        embedding_function=fake_embedding_function,
    )
    yield store
    store.close()


def fold(memory, session_id, texts, ts_minute, agent="hope"):
    memory.write(
        agent=agent,
        session_id=session_id,
        reason="threshold",
        span_turns=len(texts),
        summary=f"fold at {ts_minute}",
        messages=[
            {"role": "user" if i % 2 == 0 else "assistant", "content": t}
            for i, t in enumerate(texts)
        ],
    )


@pytest.mark.integration
def test_transcript_is_continuous_across_folds(memory):
    fold(memory, "s1", ["one", "two"], "19:00")
    fold(memory, "s1", ["three", "four"], "19:10")
    fold(memory, "s1", ["five", "six"], "19:20")

    transcript = memory.get_session_transcript("s1")

    assert [m.content_text for m in transcript] == [
        "one", "two", "three", "four", "five", "six",
    ]


@pytest.mark.integration
def test_transcript_preserves_alternating_roles(memory):
    fold(memory, "s1", ["q1", "a1", "q2", "a2"], "19:00")

    roles = [m.role for m in memory.get_session_transcript("s1")]
    assert roles == ["user", "assistant", "user", "assistant"]


@pytest.mark.integration
def test_transcript_excludes_other_sessions(memory):
    fold(memory, "s1", ["mine"], "19:00")
    fold(memory, "s2", ["theirs"], "19:05")

    assert [m.content_text for m in memory.get_session_transcript("s1")] == ["mine"]


@pytest.mark.integration
def test_transcript_of_unknown_session_is_empty(memory):
    assert memory.get_session_transcript("never-happened") == []


@pytest.mark.integration
def test_transcript_can_be_scoped_to_one_agent(memory):
    fold(memory, "shared", ["hope turn"], "19:00", agent="hope")
    fold(memory, "shared", ["atlas turn"], "19:05", agent="atlas")

    assert [m.content_text for m in memory.get_session_transcript("shared", "hope")] == [
        "hope turn"
    ]
    assert len(memory.get_session_transcript("shared")) == 2


@pytest.mark.integration
def test_list_sessions_and_transcript_agree(memory):
    """The sidebar shows a message count from list_sessions() and the panel
    renders get_session_transcript() — a mismatch reads as missing messages."""
    fold(memory, "s1", ["a", "b", "c"], "19:00")
    fold(memory, "s1", ["d", "e"], "19:10")

    session = memory.list_sessions()[0]
    assert session.message_count == len(memory.get_session_transcript("s1")) == 5

"""Unit tests for the EpisodicMemory facade (episodic.py + vector_store.py wiring).

Requires `chromadb`; skipped entirely if it isn't installed yet.
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


@pytest.mark.unit
def test_write_returns_episode_id(memory):
    episode_id = memory.write(
        agent="hope",
        session_id="sess-1",
        reason="threshold",
        span_turns=2,
        summary="Pavan and HOPE discussed deployment steps.",
        messages=[{"role": "user", "content": "how do I deploy this?"}],
    )

    assert episode_id.startswith("ep_")


@pytest.mark.unit
def test_query_hydrates_full_episode_from_summary_match(memory):
    memory.write(
        agent="hope",
        session_id="sess-1",
        reason="threshold",
        span_turns=1,
        summary="a conversation about deployment steps",
        messages=[{"role": "user", "content": "how do I deploy this?"}],
    )

    results = memory.query("deployment steps", k=1)

    assert len(results) == 1
    assert results[0].agent == "hope"
    assert results[0].messages[0].content_text == "how do I deploy this?"


@pytest.mark.unit
def test_query_with_no_matching_data_returns_empty_list(memory):
    assert memory.query("nothing has been written yet", k=5) == []

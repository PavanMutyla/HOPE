"""
Integration tests for the coordination pool end-to-end — real SQLite temp
file (not mocks), multiple agents posting/claiming/completing tasks and
exchanging signals, and the hand-off into real episodic memory when a task
resolves. See docs/HOPE_Coordination_Pool_Design.md.
"""

import pytest

chromadb = pytest.importorskip("chromadb")

from memory.coordination.store import Blackboard  # noqa: E402
from memory.episodic_memory.store import EpisodicMemory  # noqa: E402


@pytest.fixture
def episodic_memory(tmp_path, fake_embedding_function):
    store = EpisodicMemory(
        db_path=tmp_path / "episodic.db",
        media_dir=tmp_path / "media",
        persist_dir=tmp_path / "chroma",
        embedding_function=fake_embedding_function,
    )
    yield store
    store.close()


@pytest.fixture
def blackboard(tmp_path, episodic_memory):
    board = Blackboard(episodic_memory, db_path=tmp_path / "blackboard.db")
    yield board
    board.close()


@pytest.mark.integration
def test_full_task_lifecycle_across_two_agents(blackboard, episodic_memory):
    """hope posts a task, atlas claims and works it, then completes it —
    the completion both clears it from active tasks and lands a real
    episode in the shared episodic store."""
    task_id = blackboard.post_task("reorganize the downloads folder", "hope")

    assert [t.task_id for t in blackboard.get_active_tasks()] == [task_id]

    assert blackboard.claim_task(task_id, "atlas") is True
    assert blackboard.get_active_tasks(agent_name="atlas")[0].task_id == task_id

    blackboard.update_task_status(task_id, "in_progress")
    assert blackboard.get_active_tasks()[0].status == "in_progress"

    blackboard.update_task_status(task_id, "completed", detail="moved 12 files")

    assert blackboard.get_active_tasks() == []

    episodes = episodic_memory.list_by_reason("task_complete")
    assert len(episodes) == 1
    assert episodes[0].agent == "atlas"
    assert "reorganize the downloads folder" in episodes[0].summary
    assert "moved 12 files" in episodes[0].summary


@pytest.mark.integration
def test_two_agents_racing_to_claim_the_same_task_only_one_wins(blackboard):
    task_id = blackboard.post_task("shared task", "hope")

    first_claim = blackboard.claim_task(task_id, "atlas")
    second_claim = blackboard.claim_task(task_id, "hope")

    assert (first_claim, second_claim) == (True, False)
    assert blackboard.get_active_tasks(agent_name="atlas")[0].task_id == task_id
    assert blackboard.get_active_tasks(agent_name="hope") == []


@pytest.mark.integration
def test_failed_task_still_writes_an_episode(blackboard, episodic_memory):
    task_id = blackboard.post_task("a risky task", "hope")
    blackboard.claim_task(task_id, "atlas")

    blackboard.update_task_status(task_id, "failed", detail="workspace was locked")

    episodes = episodic_memory.list_by_reason("task_complete")
    assert len(episodes) == 1
    assert "workspace was locked" in episodes[0].summary


@pytest.mark.integration
def test_multiple_agents_posting_tasks_independently(blackboard):
    hope_task = blackboard.post_task("hope's task", "hope")
    atlas_task = blackboard.post_task("atlas's task", "atlas")

    active_ids = {t.task_id for t in blackboard.get_active_tasks()}

    assert active_ids == {hope_task, atlas_task}


@pytest.mark.integration
def test_signal_round_trip_unread_then_consumed(blackboard):
    blackboard.send_signal("hope", "atlas", "the disk is almost full")

    first_fetch = blackboard.get_signals_for("atlas")
    second_fetch = blackboard.get_signals_for("atlas")

    assert [s.payload for s in first_fetch] == ["the disk is almost full"]
    assert first_fetch[0].from_agent == "hope"
    assert second_fetch == []


@pytest.mark.integration
def test_signals_are_point_to_point_only(blackboard):
    blackboard.send_signal("hope", "atlas", "for atlas only")

    assert blackboard.get_signals_for("hope") == []
    assert [s.payload for s in blackboard.get_signals_for("atlas")] == ["for atlas only"]

"""Unit tests for the Blackboard facade (coordination.py wiring + the
episodic task_complete hand-off)."""

from unittest.mock import MagicMock

import pytest

from memory.coordination.store import Blackboard

pytestmark = pytest.mark.unit


@pytest.fixture
def episodic_memory():
    return MagicMock()


@pytest.fixture
def blackboard(tmp_path, episodic_memory):
    board = Blackboard(episodic_memory, db_path=tmp_path / "blackboard.db")
    yield board
    board.close()


def test_post_task_returns_prefixed_ulid(blackboard):
    task_id = blackboard.post_task("clean up notes", "hope")
    assert task_id.startswith("task_")


def test_claim_task_round_trips(blackboard):
    task_id = blackboard.post_task("clean up notes", "hope")

    assert blackboard.claim_task(task_id, "atlas") is True
    assert blackboard.claim_task(task_id, "someone_else") is False


def test_get_active_tasks_round_trips(blackboard):
    task_id = blackboard.post_task("clean up notes", "hope")

    active = blackboard.get_active_tasks()

    assert [t.task_id for t in active] == [task_id]


def test_send_and_get_signals_round_trip(blackboard):
    blackboard.send_signal("hope", "atlas", "check the logs")

    signals = blackboard.get_signals_for("atlas")

    assert [s.payload for s in signals] == ["check the logs"]


def test_update_task_status_to_completed_triggers_one_episodic_write(blackboard, episodic_memory):
    task_id = blackboard.post_task("clean up notes", "hope")
    blackboard.claim_task(task_id, "atlas")

    blackboard.update_task_status(task_id, "completed", detail="all done")

    episodic_memory.write.assert_called_once()
    _, kwargs = episodic_memory.write.call_args
    assert kwargs["reason"] == "task_complete"
    assert kwargs["agent"] == "atlas"


def test_update_task_status_to_failed_triggers_one_episodic_write(blackboard, episodic_memory):
    task_id = blackboard.post_task("clean up notes", "hope")

    blackboard.update_task_status(task_id, "failed", detail="ran into a problem")

    episodic_memory.write.assert_called_once()
    _, kwargs = episodic_memory.write.call_args
    assert kwargs["reason"] == "task_complete"
    assert kwargs["agent"] == "hope"  # falls back to created_by when unclaimed


def test_update_task_status_to_in_progress_does_not_write_episodic(blackboard, episodic_memory):
    task_id = blackboard.post_task("clean up notes", "hope")

    blackboard.update_task_status(task_id, "in_progress")

    episodic_memory.write.assert_not_called()


def test_update_task_status_on_missing_task_returns_false_and_does_not_write(
    blackboard, episodic_memory
):
    result = blackboard.update_task_status("task_does_not_exist", "completed")

    assert result is False
    episodic_memory.write.assert_not_called()

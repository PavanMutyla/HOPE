"""Unit tests for the coordination-pool SQLite layer — task posting/claiming/
status updates and signal send/receive. See
memory/coordination/migrations/0001_init.sql for the schema."""

import threading

import pytest

from memory.coordination import coordination

pytestmark = pytest.mark.unit


@pytest.fixture
def conn(tmp_path):
    connection = coordination.connect(tmp_path / "blackboard.db")
    yield connection
    connection.close()


def test_post_task_returns_prefixed_ulid(conn):
    task_id = coordination.post_task(conn, "clean up notes", "hope")
    assert task_id.startswith("task_")


def test_post_task_starts_open_with_no_owner(conn):
    task_id = coordination.post_task(conn, "clean up notes", "hope")
    task = coordination.get_task(conn, task_id)

    assert task.description == "clean up notes"
    assert task.owner_agent is None
    assert task.status == "open"
    assert task.created_by == "hope"


def test_get_task_returns_none_for_missing_id(conn):
    assert coordination.get_task(conn, "task_does_not_exist") is None


def test_claim_task_succeeds_on_unclaimed_task(conn):
    task_id = coordination.post_task(conn, "clean up notes", "hope")

    claimed = coordination.claim_task(conn, task_id, "atlas")

    assert claimed is True
    task = coordination.get_task(conn, task_id)
    assert task.owner_agent == "atlas"
    assert task.status == "claimed"


def test_claim_task_fails_on_already_claimed_task(conn):
    task_id = coordination.post_task(conn, "clean up notes", "hope")
    coordination.claim_task(conn, task_id, "atlas")

    claimed_again = coordination.claim_task(conn, task_id, "someone_else")

    assert claimed_again is False
    task = coordination.get_task(conn, task_id)
    assert task.owner_agent == "atlas"


def test_claim_task_fails_on_missing_task(conn):
    assert coordination.claim_task(conn, "task_does_not_exist", "atlas") is False


def test_claim_task_race_exactly_one_winner(tmp_path):
    """Two agents racing to claim the same task is the concrete failure this
    tier exists to prevent — assert exactly one of two concurrent claims
    wins, using separate connections to the same file like real agents
    would."""
    db_path = tmp_path / "blackboard.db"
    setup_conn = coordination.connect(db_path)
    task_id = coordination.post_task(setup_conn, "race me", "hope")
    setup_conn.close()

    results: list[bool] = []
    barrier = threading.Barrier(2)

    def attempt_claim(agent: str) -> None:
        conn = coordination.connect(db_path)
        barrier.wait()
        results.append(coordination.claim_task(conn, task_id, agent))
        conn.close()

    threads = [
        threading.Thread(target=attempt_claim, args=("atlas",)),
        threading.Thread(target=attempt_claim, args=("hope",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [False, True]


def test_update_task_status_updates_status(conn):
    task_id = coordination.post_task(conn, "clean up notes", "hope")

    updated = coordination.update_task_status(conn, task_id, "in_progress")

    assert updated is True
    assert coordination.get_task(conn, task_id).status == "in_progress"


def test_update_task_status_with_detail_overwrites_payload(conn):
    task_id = coordination.post_task(conn, "clean up notes", "hope")

    coordination.update_task_status(conn, task_id, "completed", detail="all done")

    task = coordination.get_task(conn, task_id)
    assert task.status == "completed"
    assert task.payload == "all done"


def test_update_task_status_returns_false_for_missing_task(conn):
    assert coordination.update_task_status(conn, "task_does_not_exist", "completed") is False


def test_get_active_tasks_excludes_completed_and_failed(conn):
    open_id = coordination.post_task(conn, "still open", "hope")
    done_id = coordination.post_task(conn, "done", "hope")
    coordination.update_task_status(conn, done_id, "completed")

    active = coordination.get_active_tasks(conn)

    assert [t.task_id for t in active] == [open_id]


def test_get_active_tasks_filters_by_owner(conn):
    atlas_task = coordination.post_task(conn, "atlas task", "hope")
    coordination.claim_task(conn, atlas_task, "atlas")
    hope_task = coordination.post_task(conn, "hope task", "hope")
    coordination.claim_task(conn, hope_task, "hope")

    atlas_active = coordination.get_active_tasks(conn, agent_name="atlas")

    assert [t.task_id for t in atlas_active] == [atlas_task]


def test_get_active_tasks_on_empty_store_returns_empty_list(conn):
    assert coordination.get_active_tasks(conn) == []


def test_send_signal_returns_prefixed_ulid(conn):
    signal_id = coordination.send_signal(conn, "hope", "atlas", "check the logs")
    assert signal_id.startswith("sig_")


def test_get_signals_for_returns_unread_and_marks_them_read(conn):
    coordination.send_signal(conn, "hope", "atlas", "first message")

    first_fetch = coordination.get_signals_for(conn, "atlas")
    second_fetch = coordination.get_signals_for(conn, "atlas")

    assert [s.payload for s in first_fetch] == ["first message"]
    assert second_fetch == []


def test_get_signals_for_only_returns_signals_addressed_to_agent(conn):
    coordination.send_signal(conn, "hope", "atlas", "for atlas")
    coordination.send_signal(conn, "atlas", "hope", "for hope")

    atlas_signals = coordination.get_signals_for(conn, "atlas")

    assert [s.payload for s in atlas_signals] == ["for atlas"]


def test_get_signals_for_on_empty_store_returns_empty_list(conn):
    assert coordination.get_signals_for(conn, "atlas") == []

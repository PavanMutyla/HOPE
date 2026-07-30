"""Unit tests for the plan-tracking SQLite layer — see
migrations/0002_add_plans.sql. Unlike episodes, a plan is written before
anything happens and mutated in place as it resolves."""

import pytest

from memory.episodic_memory import episodic, plans

pytestmark = pytest.mark.unit


@pytest.fixture
def conn(tmp_path):
    connection = episodic.connect(tmp_path / "episodic.db")
    yield connection
    connection.close()


@pytest.fixture
def media_dir(tmp_path):
    return tmp_path / "media"


def test_create_plan_returns_prefixed_ulid(conn):
    plan_id = plans.create_plan(conn, "atlas", "clean up the notes folder")

    assert plan_id.startswith("plan_")


def test_create_plan_starts_pending_with_no_resolution(conn):
    plan_id = plans.create_plan(conn, "atlas", "clean up the notes folder")

    plan = plans.get_plan(conn, plan_id)

    assert plan.agent == "atlas"
    assert plan.description == "clean up the notes folder"
    assert plan.status == "pending"
    assert plan.resolved_at is None
    assert plan.resulting_episode_id is None
    assert plan.superseded_by is None


def test_get_plan_returns_none_for_missing_id(conn):
    assert plans.get_plan(conn, "plan_does_not_exist") is None


def test_resolve_plan_marks_completed_and_links_episode(conn, media_dir):
    plan_id = plans.create_plan(conn, "atlas", "list the files")
    episode_id = episodic.create_episode(
        conn, media_dir, "atlas", "sess-1", "task_complete", 2, "did it",
        [{"role": "user", "content": "list files"}],
    )

    plans.resolve_plan(conn, plan_id, episode_id)
    plan = plans.get_plan(conn, plan_id)

    assert plan.status == "completed"
    assert plan.resulting_episode_id == episode_id
    assert plan.resolved_at is not None


def test_abandon_plan_marks_abandoned_with_no_episode_link(conn):
    plan_id = plans.create_plan(conn, "atlas", "reorganize downloads")

    plans.abandon_plan(conn, plan_id)
    plan = plans.get_plan(conn, plan_id)

    assert plan.status == "abandoned"
    assert plan.resulting_episode_id is None
    assert plan.resolved_at is not None


def test_supersede_plan_marks_superseded_and_points_at_replacement(conn):
    old_plan_id = plans.create_plan(conn, "atlas", "backup the old way")
    new_plan_id = plans.create_plan(conn, "atlas", "backup the new way")

    plans.supersede_plan(conn, old_plan_id, new_plan_id)
    old_plan = plans.get_plan(conn, old_plan_id)

    assert old_plan.status == "superseded"
    assert old_plan.superseded_by == new_plan_id


def test_list_plans_filters_by_agent(conn):
    plans.create_plan(conn, "atlas", "atlas task")
    plans.create_plan(conn, "hope", "hope task")

    atlas_plans = plans.list_plans(conn, agent="atlas")

    assert [p.description for p in atlas_plans] == ["atlas task"]


def test_list_plans_filters_by_status(conn):
    pending_id = plans.create_plan(conn, "atlas", "still pending")
    done_id = plans.create_plan(conn, "atlas", "already done")
    plans.abandon_plan(conn, done_id)

    pending_only = plans.list_plans(conn, agent="atlas", status="pending")

    assert [p.id for p in pending_only] == [pending_id]
    assert done_id not in [p.id for p in pending_only]


def test_list_plans_with_no_filters_returns_everything_newest_first(conn):
    first_id = plans.create_plan(conn, "atlas", "first", ts="2026-01-01T00:00:00+00:00")
    second_id = plans.create_plan(conn, "atlas", "second", ts="2026-01-02T00:00:00+00:00")

    all_plans = plans.list_plans(conn)

    assert [p.id for p in all_plans] == [second_id, first_id]


def test_list_plans_on_empty_store_returns_empty_list(conn):
    assert plans.list_plans(conn) == []

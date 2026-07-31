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


@pytest.mark.unit
def test_query_with_agent_only_returns_that_agents_episodes(memory):
    memory.write(
        agent="hope",
        session_id="sess-1",
        reason="threshold",
        span_turns=1,
        summary="a conversation about deployment steps",
        messages=[{"role": "user", "content": "how do I deploy this?"}],
    )
    memory.write(
        agent="atlas",
        session_id="sess-1",
        reason="threshold",
        span_turns=1,
        summary="a conversation about deployment steps",
        messages=[{"role": "user", "content": "deploy the atlas workspace"}],
    )

    results = memory.query("deployment steps", k=5, agent="hope")

    assert len(results) == 1
    assert results[0].agent == "hope"


@pytest.mark.unit
def test_list_by_reason_returns_only_matching_episodes(memory):
    memory.write(
        agent="hope", session_id="sess-1", reason="session_end_raw", span_turns=1,
        summary="raw dump", messages=[{"role": "user", "content": "hi"}],
    )
    memory.write(
        agent="hope", session_id="sess-2", reason="threshold", span_turns=1,
        summary="folded", messages=[{"role": "user", "content": "yo"}],
    )

    pending = memory.list_by_reason("session_end_raw")

    assert len(pending) == 1
    assert pending[0].summary == "raw dump"


@pytest.mark.unit
def test_upgrade_replaces_summary_and_is_findable_by_new_reason(memory):
    episode_id = memory.write(
        agent="hope", session_id="sess-1", reason="session_end_raw", span_turns=1,
        summary="raw dump", messages=[{"role": "user", "content": "deployment talk"}],
    )

    memory.upgrade(episode_id, "hope", "a real summary about deployment", "session_end")

    assert memory.list_by_reason("session_end_raw") == []
    [upgraded] = memory.list_by_reason("session_end")
    assert upgraded.summary == "a real summary about deployment"


@pytest.mark.unit
def test_upgrade_updates_the_vector_index_so_the_new_summary_is_searchable(memory):
    episode_id = memory.write(
        agent="hope", session_id="sess-1", reason="session_end_raw", span_turns=1,
        summary="completely unrelated placeholder text",
        messages=[{"role": "user", "content": "hi"}],
    )

    memory.upgrade(episode_id, "hope", "a chat about rocket engines", "session_end")

    results = memory.query("rocket engines", k=5, agent="hope")
    assert any(e.id == episode_id for e in results)


@pytest.mark.unit
def test_get_latest_by_reason_returns_the_most_recent_episode(memory):
    memory.write(
        agent="hope", session_id="sess-1", reason="session_end", span_turns=1,
        summary="older session", messages=[{"role": "user", "content": "a"}],
    )
    memory.write(
        agent="hope", session_id="sess-2", reason="session_end", span_turns=1,
        summary="newer session", messages=[{"role": "user", "content": "b"}],
    )

    latest = memory.get_latest_by_reason("session_end", agent="hope")

    assert latest.summary == "newer session"


@pytest.mark.unit
def test_get_latest_by_reason_with_no_match_returns_none(memory):
    assert memory.get_latest_by_reason("session_end", agent="hope") is None


@pytest.mark.unit
def test_write_works_from_a_different_thread_than_construction(memory):
    """Regression test: every real write path (ContextSummarizer, Atlas) calls
    EpisodicMemory.write via asyncio.to_thread, so the connection is created
    on one thread and used from another. sqlite3 forbids this unless
    check_same_thread=False was passed at connect() time (episodic.py)."""
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        episode_id = pool.submit(
            memory.write,
            agent="hope",
            session_id="sess-1",
            reason="threshold",
            span_turns=1,
            summary="cross-thread write",
            messages=[{"role": "user", "content": "hello from another thread"}],
        ).result()

    assert episode_id.startswith("ep_")


@pytest.mark.unit
def test_query_without_agent_returns_episodes_from_any_agent(memory):
    memory.write(
        agent="hope",
        session_id="sess-1",
        reason="threshold",
        span_turns=1,
        summary="a conversation about deployment steps",
        messages=[{"role": "user", "content": "how do I deploy this?"}],
    )
    memory.write(
        agent="atlas",
        session_id="sess-1",
        reason="threshold",
        span_turns=1,
        summary="a conversation about deployment steps",
        messages=[{"role": "user", "content": "deploy the atlas workspace"}],
    )

    results = memory.query("deployment steps", k=5)

    assert {e.agent for e in results} == {"hope", "atlas"}


# ── Plan tracking ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_create_plan_returns_prefixed_ulid(memory):
    plan_id = memory.create_plan("atlas", "clean up the notes folder")

    assert plan_id.startswith("plan_")


@pytest.mark.unit
def test_get_plan_round_trips(memory):
    plan_id = memory.create_plan("atlas", "clean up the notes folder")

    plan = memory.get_plan(plan_id)

    assert plan.agent == "atlas"
    assert plan.description == "clean up the notes folder"
    assert plan.status == "pending"


@pytest.mark.unit
def test_resolve_plan_links_the_resulting_episode(memory):
    plan_id = memory.create_plan("atlas", "list the files")
    episode_id = memory.write(
        agent="atlas", session_id="sess-1", reason="task_complete", span_turns=1,
        summary="did it", messages=[{"role": "user", "content": "list files"}],
    )

    memory.resolve_plan(plan_id, episode_id)

    plan = memory.get_plan(plan_id)
    assert plan.status == "completed"
    assert plan.resulting_episode_id == episode_id


@pytest.mark.unit
def test_abandon_plan_marks_it_abandoned(memory):
    plan_id = memory.create_plan("atlas", "reorganize downloads")

    memory.abandon_plan(plan_id)

    assert memory.get_plan(plan_id).status == "abandoned"


@pytest.mark.unit
def test_supersede_plan_points_at_the_replacement(memory):
    old_plan_id = memory.create_plan("atlas", "backup the old way")
    new_plan_id = memory.create_plan("atlas", "backup the new way")

    memory.supersede_plan(old_plan_id, new_plan_id)

    old_plan = memory.get_plan(old_plan_id)
    assert old_plan.status == "superseded"
    assert old_plan.superseded_by == new_plan_id


@pytest.mark.unit
def test_list_plans_filters_by_agent_and_status(memory):
    pending_id = memory.create_plan("atlas", "still pending")
    done_id = memory.create_plan("atlas", "already done")
    memory.abandon_plan(done_id)
    memory.create_plan("hope", "a hope plan")

    atlas_pending = memory.list_plans(agent="atlas", status="pending")

    assert [p.id for p in atlas_pending] == [pending_id]

"""Unit tests for the sub-agent and research-run tables in memory/coordination/,
against a real SQLite file."""

import pytest

from memory.coordination import coordination


@pytest.fixture
def conn(tmp_path):
    connection = coordination.connect(tmp_path / "blackboard.db")
    yield connection
    connection.close()


@pytest.mark.unit
def test_migrations_are_idempotent(tmp_path):
    coordination.connect(tmp_path / "b.db").close()
    coordination.connect(tmp_path / "b.db").close()


@pytest.mark.unit
def test_registered_agent_starts_working(conn):
    agent_id = coordination.register_agent(conn, "Emma", "researcher", "bf_emma", "Find X")
    agent = coordination.get_agent(conn, agent_id)
    assert agent.agent_id.startswith("agt_")
    assert agent.status == "working"
    assert agent.spoken_name == "Emma"
    assert agent.retired_at is None


@pytest.mark.unit
def test_set_agent_status_to_retired_stamps_retired_at(conn):
    agent_id = coordination.register_agent(conn, "Emma", "researcher", "bf_emma", "Find X")
    assert coordination.set_agent_status(conn, agent_id, "retired")
    assert coordination.get_agent(conn, agent_id).retired_at is not None


@pytest.mark.unit
def test_set_agent_status_on_missing_agent_returns_false(conn):
    assert coordination.set_agent_status(conn, "agt_missing", "idle") is False


@pytest.mark.unit
def test_list_agents_hides_retired_by_default(conn):
    live = coordination.register_agent(conn, "Emma", "researcher", "bf_emma", "A")
    gone = coordination.register_agent(conn, "Nicole", "researcher", "af_nicole", "B")
    coordination.set_agent_status(conn, gone, "retired")
    assert [a.agent_id for a in coordination.list_agents(conn)] == [live]
    assert len(coordination.list_agents(conn, include_retired=True)) == 2


@pytest.mark.unit
def test_retire_live_agents_sweeps_every_leftover(conn):
    coordination.register_agent(conn, "Emma", "researcher", "bf_emma", "A")
    idle = coordination.register_agent(conn, "Nicole", "researcher", "af_nicole", "B")
    coordination.set_agent_status(conn, idle, "idle")
    assert coordination.retire_live_agents(conn) == 2
    assert coordination.list_agents(conn) == []


@pytest.mark.unit
def test_run_starts_in_planning(conn):
    run_id = coordination.create_run(conn, "What is X?")
    run = coordination.get_run(conn, run_id)
    assert run.run_id.startswith("run_")
    assert run.status == "planning"


@pytest.mark.unit
def test_status_only_update_keeps_report_and_summary(conn):
    run_id = coordination.create_run(conn, "Q")
    coordination.update_run(conn, run_id, "completed", "/r/report.md", "It's X.")
    coordination.update_run(conn, run_id, "completed")
    run = coordination.get_run(conn, run_id)
    assert run.report_path == "/r/report.md"
    assert run.summary == "It's X."


@pytest.mark.unit
def test_list_runs_is_newest_first(conn):
    first = coordination.create_run(conn, "first")
    second = coordination.create_run(conn, "second")
    assert [r.run_id for r in coordination.list_runs(conn)] == [second, first]


@pytest.mark.unit
def test_same_agent_reading_same_url_twice_is_one_source(conn):
    run_id = coordination.create_run(conn, "Q")
    assert coordination.add_source(conn, run_id, "agt_1", "https://a.org", "A", "h1")
    assert not coordination.add_source(conn, run_id, "agt_1", "https://a.org", "A", "h1")
    assert len(coordination.list_sources(conn, run_id)) == 1


@pytest.mark.unit
def test_two_agents_reading_same_url_are_two_sources(conn):
    run_id = coordination.create_run(conn, "Q")
    coordination.add_source(conn, run_id, "agt_1", "https://a.org", "A", "h1")
    coordination.add_source(conn, run_id, "agt_2", "https://a.org", "A", "h1")
    assert len(coordination.list_sources(conn, run_id)) == 2

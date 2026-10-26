"""Unit tests for core/agents/manager.py — spawn/retire keep the registry, the
voice pool and the blackboard's agents table in step. Real AgentRegistry,
real VoicePool, real Blackboard on a temp SQLite file."""

import asyncio
from unittest.mock import MagicMock

import pytest

from core.agents.manager import SubAgentLimitReached, SubAgentManager
from core.agents.spec import SubAgentSpec
from core.voice.agent import AgentRegistry, VoiceAgent
from core.voice.voice_pool import PooledVoice, VoicePool
from memory.coordination.store import Blackboard


def _spec(objective="Find X"):
    return SubAgentSpec(
        template="researcher", objective=objective, output_format="md",
        boundaries="none", tools=["web_search"], max_tool_calls=3,
    )


def _prompt(live):
    return f"I am {live.spoken_name}, status {live.status}"


@pytest.fixture
def blackboard(tmp_path):
    board = Blackboard(MagicMock(), db_path=tmp_path / "blackboard.db")
    yield board
    board.close()


@pytest.fixture
def registry():
    reg = AgentRegistry()
    reg.register(VoiceAgent(name="hope", system_prompt="You are HOPE.", voice_id="af_heart"))
    return reg


def _manager(registry, blackboard, max_live=5, pool=None):
    return SubAgentManager(registry, blackboard, pool or VoicePool(), max_live)


@pytest.mark.unit
async def test_spawn_registers_agent_under_its_spoken_name(registry, blackboard):
    manager = _manager(registry, blackboard)
    live = await manager.spawn(_spec(), _prompt)
    assert registry.find(live.spoken_name) is live.voice_agent
    assert registry.get(live.spoken_name.lower()).voice_id == live.voice_id


@pytest.mark.unit
async def test_spawn_writes_a_working_row_to_the_blackboard(registry, blackboard):
    live = await _manager(registry, blackboard).spawn(_spec(), _prompt, run_id="run_1")
    row = blackboard.get_agent(live.agent_id)
    assert (row.status, row.voice_id, row.run_id) == ("working", live.voice_id, "run_1")


@pytest.mark.unit
async def test_two_spawns_get_different_voices(registry, blackboard):
    manager = _manager(registry, blackboard)
    first, second = await manager.spawn(_spec("a"), _prompt), await manager.spawn(_spec("b"), _prompt)
    assert first.voice_id != second.voice_id
    assert first.spoken_name != second.spoken_name


@pytest.mark.unit
async def test_voice_prompt_is_built_from_live_state_each_time(registry, blackboard):
    manager = _manager(registry, blackboard)
    live = await manager.spawn(_spec(), _prompt)
    assert "status working" in live.voice_agent.current_prompt()
    await manager.set_status(live, "idle")
    assert "status idle" in live.voice_agent.current_prompt()


@pytest.mark.unit
async def test_retire_unregisters_releases_voice_and_marks_row(registry, blackboard):
    pool = VoicePool()
    manager = _manager(registry, blackboard, pool=pool)
    live = await manager.spawn(_spec(), _prompt)
    before = pool.available()

    assert await manager.retire(live.spoken_name.upper())  # case-insensitive
    assert registry.find(live.spoken_name) is None
    assert pool.available() == before + 1
    assert blackboard.get_agent(live.agent_id).status == "retired"
    assert manager.live() == []


@pytest.mark.unit
async def test_retire_unknown_name_returns_false(registry, blackboard):
    assert await _manager(registry, blackboard).retire("nobody") is False


@pytest.mark.unit
async def test_retire_cancels_a_running_task(registry, blackboard):
    manager = _manager(registry, blackboard)
    live = await manager.spawn(_spec(), _prompt)
    live.task = asyncio.create_task(asyncio.sleep(60))
    await manager.retire(live.name)
    await asyncio.sleep(0)
    assert live.task.cancelled()


@pytest.mark.unit
async def test_at_cap_the_oldest_idle_agent_makes_room(registry, blackboard):
    manager = _manager(registry, blackboard, max_live=2)
    oldest = await manager.spawn(_spec("a"), _prompt)
    await manager.spawn(_spec("b"), _prompt)
    await manager.set_status(oldest, "idle")

    newest = await manager.spawn(_spec("c"), _prompt)
    live_ids = {live.agent_id for live in manager.live()}
    assert oldest.agent_id not in live_ids
    assert newest.agent_id in live_ids
    assert blackboard.get_agent(oldest.agent_id).status == "retired"


@pytest.mark.unit
async def test_at_cap_working_agents_are_never_evicted(registry, blackboard):
    manager = _manager(registry, blackboard, max_live=1)
    working = await manager.spawn(_spec("a"), _prompt)
    with pytest.raises(SubAgentLimitReached):
        await manager.spawn(_spec("b"), _prompt)
    assert manager.find(working.name) is working


@pytest.mark.unit
async def test_exhausted_voice_pool_refuses_spawn(registry, blackboard):
    pool = VoicePool(pool=(PooledVoice("af_sarah", "Sarah"),))
    manager = _manager(registry, blackboard, pool=pool)
    await manager.spawn(_spec("a"), _prompt)
    with pytest.raises(SubAgentLimitReached):
        await manager.spawn(_spec("b"), _prompt)


@pytest.mark.unit
async def test_startup_retires_rows_left_by_a_killed_run(registry, blackboard):
    leftover = blackboard.register_agent("Emma", "researcher", "bf_emma", "old")
    await _manager(registry, blackboard).startup()
    assert blackboard.get_agent(leftover).status == "retired"


@pytest.mark.unit
async def test_retire_all_empties_everything(registry, blackboard):
    manager = _manager(registry, blackboard)
    await manager.spawn(_spec("a"), _prompt)
    await manager.spawn(_spec("b"), _prompt)
    await manager.retire_all()
    assert manager.live() == []
    assert blackboard.list_agents() == []
    assert [a.name for a in registry.all()] == ["hope"]


@pytest.mark.unit
async def test_is_subagent_only_for_spawned_agents(registry, blackboard):
    manager = _manager(registry, blackboard)
    live = await manager.spawn(_spec(), _prompt)
    assert manager.is_subagent(live.name)
    assert not manager.is_subagent("hope")
    assert not manager.is_subagent("atlas")

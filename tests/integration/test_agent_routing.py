"""
Integration tests for voice agent routing — connect and handback handlers.

Tests that the connect_to_agent and handback_to_hope tool handlers correctly
invoke the orchestrator's switch_to() and update active agent state.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.integration
async def test_connect_to_agent_atlas_switches_active_agent(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_connect_handler

    agent_state.active = "hope"
    handler = _make_connect_handler(mock_orchestrator)

    mock_params = MagicMock(arguments={"name": "atlas"})
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    assert agent_state.active == "atlas"


@pytest.mark.integration
async def test_connect_to_agent_atlas_updates_status_panel(mock_orchestrator):
    """switch_to() must update the status panel's active agent for the dashboard."""
    from core.voice.agent_state import agent_state
    from tools.registry import _make_connect_handler

    agent_state.active = "hope"
    handler = _make_connect_handler(mock_orchestrator)

    mock_params = MagicMock(arguments={"name": "atlas"})
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.panel.set_agent.assert_called_once_with("atlas")


@pytest.mark.integration
async def test_connect_to_agent_atlas_calls_result_callback(mock_orchestrator):
    from tools.registry import _make_connect_handler

    handler = _make_connect_handler(mock_orchestrator)
    mock_params = MagicMock(arguments={"name": "atlas"})
    mock_params.result_callback = AsyncMock()

    await handler(mock_params)

    mock_params.result_callback.assert_called_once()


@pytest.mark.integration
async def test_handback_to_hope_switches_active_agent(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_handback_handler

    agent_state.active = "atlas"
    handler = _make_handback_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    assert agent_state.active == "hope"


@pytest.mark.integration
async def test_handback_to_hope_calls_result_callback(mock_orchestrator):
    from tools.registry import _make_handback_handler

    handler = _make_handback_handler(mock_orchestrator)
    mock_params = MagicMock()
    mock_params.result_callback = AsyncMock()

    await handler(mock_params)

    mock_params.result_callback.assert_called_once()


@pytest.mark.integration
async def test_connect_updates_system_prompt_to_atlas(mock_orchestrator):
    """After connect, the pipeline context should carry Atlas's system prompt."""
    from tools.registry import _make_connect_handler

    handler = _make_connect_handler(mock_orchestrator)
    mock_params = MagicMock(arguments={"name": "atlas"})
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    updated = mock_orchestrator.bundle.context.set_messages.call_args[0][0]
    assert updated[0]["content"] == "You are Atlas."


@pytest.mark.integration
async def test_handback_updates_system_prompt_to_hope(mock_orchestrator):
    """After handback, the pipeline context should carry HOPE's system prompt."""
    from core.voice.agent_state import agent_state
    from tools.registry import _make_connect_handler, _make_handback_handler

    # First connect to atlas, then hand back
    agent_state.active = "hope"
    connect = _make_connect_handler(mock_orchestrator)
    await connect(MagicMock(arguments={"name": "atlas"}, result_callback=AsyncMock()))

    # Reset context mock call count for clean assertion
    mock_orchestrator.bundle.context.set_messages.reset_mock()
    mock_orchestrator.bundle.context.messages = [{"role": "system", "content": "You are Atlas."}]

    handback = _make_handback_handler(mock_orchestrator)
    await handback(MagicMock(result_callback=AsyncMock()))

    updated = mock_orchestrator.bundle.context.set_messages.call_args[0][0]
    assert updated[0]["content"] == "You are HOPE."


# ─── Dynamic sub-agents ──────────────────────────────────────────

def _register_emma(mock_orchestrator):
    from core.voice.agent import VoiceAgent

    emma = VoiceAgent(name="emma", system_prompt="You are Emma.", voice_id="bf_emma", spoken_name="Emma")
    mock_orchestrator._registry.register(emma)
    return emma


@pytest.mark.integration
async def test_connect_to_researcher_by_spoken_name(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_connect_handler

    _register_emma(mock_orchestrator)
    agent_state.active = "hope"
    params = MagicMock(arguments={"name": "Emma"}, result_callback=AsyncMock())
    await _make_connect_handler(mock_orchestrator)(params)

    assert agent_state.active == "emma"
    frame = mock_orchestrator.bundle.llm.push_frame.call_args[0][0]
    assert frame.delta.voice == "bf_emma"
    assert "Emma" in params.result_callback.call_args[0][0]


@pytest.mark.integration
async def test_connect_to_unknown_agent_does_not_switch(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_connect_handler

    agent_state.active = "hope"
    params = MagicMock(arguments={"name": "Zed"}, result_callback=AsyncMock())
    await _make_connect_handler(mock_orchestrator)(params)

    assert agent_state.active == "hope"
    assert "no agent called Zed" in params.result_callback.call_args[0][0]


def _manager_with(names):
    manager = MagicMock()
    manager.is_subagent = lambda name: name in names
    return manager


@pytest.mark.integration
async def test_guard_refuses_unlisted_tools_while_a_subagent_is_active():
    from core.voice.agent_state import agent_state
    from tools.registry import _guarded

    inner = AsyncMock()
    wrapped = _guarded("delegate_to_atlas", inner, _manager_with({"emma"}))
    agent_state.active = "emma"
    params = MagicMock(result_callback=AsyncMock())
    await wrapped(params)

    inner.assert_not_called()
    assert "isn't available to a researcher" in params.result_callback.call_args[0][0]


@pytest.mark.integration
async def test_guard_lets_hope_and_atlas_call_everything():
    from core.voice.agent_state import agent_state
    from tools.registry import _guarded

    inner = AsyncMock()
    wrapped = _guarded("delegate_to_atlas", inner, _manager_with({"emma"}))
    for active in ("hope", "atlas"):
        agent_state.active = active
        await wrapped(MagicMock())
    assert inner.await_count == 2


@pytest.mark.integration
@pytest.mark.parametrize("tool", ["handback_to_hope", "connect_to_agent", "list_subagents", "research_status"])
def test_guard_leaves_subagent_voice_tools_unwrapped(tool):
    from tools.registry import _guarded

    inner = AsyncMock()
    assert _guarded(tool, inner, _manager_with({"emma"})) is inner


@pytest.mark.integration
async def test_retiring_the_active_subagent_hands_back_to_hope_first(mock_orchestrator, tmp_path):
    from core.agents.manager import SubAgentManager
    from core.agents.spec import SubAgentSpec
    from core.voice.agent_state import agent_state
    from core.voice.voice_pool import VoicePool
    from memory.coordination.store import Blackboard
    from tools.registry import _make_retire_subagent_handler

    blackboard = Blackboard(MagicMock(), db_path=tmp_path / "blackboard.db")
    manager = SubAgentManager(mock_orchestrator._registry, blackboard, VoicePool(), 5)
    spec = SubAgentSpec(
        template="researcher", objective="X", output_format="md", boundaries="",
        tools=["web_search"], max_tool_calls=2,
    )
    live = await manager.spawn(spec, lambda agent: "prompt")
    await mock_orchestrator.switch_to(live.name)
    assert agent_state.active == live.name

    params = MagicMock(arguments={"name": live.spoken_name}, result_callback=AsyncMock())
    await _make_retire_subagent_handler(mock_orchestrator, manager)(params)

    assert agent_state.active == "hope"
    assert manager.live() == []
    blackboard.close()

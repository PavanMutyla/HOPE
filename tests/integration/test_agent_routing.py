"""
Integration tests for voice agent routing — connect and handback handlers.

Tests that the connect_to_atlas and handback_to_hope tool handlers correctly
invoke the orchestrator's switch_to() and update active agent state.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.integration
async def test_connect_to_atlas_switches_active_agent(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_connect_handler

    agent_state.active = "hope"
    handler = _make_connect_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    assert agent_state.active == "atlas"


@pytest.mark.integration
async def test_connect_to_atlas_calls_result_callback(mock_orchestrator):
    from tools.registry import _make_connect_handler

    handler = _make_connect_handler(mock_orchestrator)
    mock_params = MagicMock()
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
    mock_params = MagicMock()
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
    await connect(MagicMock(result_callback=AsyncMock()))

    # Reset context mock call count for clean assertion
    mock_orchestrator.bundle.context.set_messages.reset_mock()
    mock_orchestrator.bundle.context.messages = [{"role": "system", "content": "You are Atlas."}]

    handback = _make_handback_handler(mock_orchestrator)
    await handback(MagicMock(result_callback=AsyncMock()))

    updated = mock_orchestrator.bundle.context.set_messages.call_args[0][0]
    assert updated[0]["content"] == "You are HOPE."

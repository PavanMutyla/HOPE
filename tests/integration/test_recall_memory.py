"""
Integration tests for the recall_memory tool handler — agent-scoped episodic
memory retrieval (tools/registry.py::_make_recall_memory_handler).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.integration
async def test_recall_memory_defaults_to_own_agent_history(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_recall_memory_handler

    agent_state.active = "hope"
    mock_orchestrator.bundle.episodic_memory.query = MagicMock(return_value=[])
    handler = _make_recall_memory_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "deployment steps"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.episodic_memory.query.assert_called_once_with(
        "deployment steps", 5, "hope"
    )


@pytest.mark.integration
async def test_recall_memory_with_explicit_agent_name_scopes_to_that_agent(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_recall_memory_handler

    agent_state.active = "hope"
    mock_orchestrator.bundle.episodic_memory.query = MagicMock(return_value=[])
    handler = _make_recall_memory_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "filesystem cleanup", "agent_name": "atlas"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.episodic_memory.query.assert_called_once_with(
        "filesystem cleanup", 5, "atlas"
    )


@pytest.mark.integration
async def test_recall_memory_with_all_searches_unscoped(mock_orchestrator):
    from tools.registry import _make_recall_memory_handler

    mock_orchestrator.bundle.episodic_memory.query = MagicMock(return_value=[])
    handler = _make_recall_memory_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "anything", "agent_name": "all"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.episodic_memory.query.assert_called_once_with("anything", 5, None)


@pytest.mark.integration
async def test_recall_memory_formats_results_for_callback(mock_orchestrator):
    from tools.registry import _make_recall_memory_handler

    episodes = [
        SimpleNamespace(agent="hope", summary="Pavan and HOPE discussed deployment."),
        SimpleNamespace(agent="atlas", summary="Atlas cleaned up the workspace."),
    ]
    mock_orchestrator.bundle.episodic_memory.query = MagicMock(return_value=episodes)
    handler = _make_recall_memory_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "deployment", "agent_name": "all"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    sent = mock_params.result_callback.call_args[0][0]
    assert "Pavan and HOPE discussed deployment." in sent
    assert "Atlas cleaned up the workspace." in sent


@pytest.mark.integration
async def test_recall_memory_with_no_results_returns_friendly_message(mock_orchestrator):
    from tools.registry import _make_recall_memory_handler

    mock_orchestrator.bundle.episodic_memory.query = MagicMock(return_value=[])
    handler = _make_recall_memory_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "nothing relevant"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_params.result_callback.assert_called_once_with("No matching memories found.")

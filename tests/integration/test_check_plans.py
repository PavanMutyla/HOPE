"""
Integration tests for the check_plans tool handler
(tools/registry.py::_make_check_plans_handler).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.integration
async def test_check_plans_defaults_to_own_agent_and_pending_status(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_check_plans_handler

    agent_state.active = "atlas"
    mock_orchestrator.bundle.episodic_memory.list_plans = MagicMock(return_value=[])
    handler = _make_check_plans_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.episodic_memory.list_plans.assert_called_once_with("atlas", "pending")


@pytest.mark.integration
async def test_check_plans_with_explicit_agent_and_status(mock_orchestrator):
    from tools.registry import _make_check_plans_handler

    mock_orchestrator.bundle.episodic_memory.list_plans = MagicMock(return_value=[])
    handler = _make_check_plans_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"agent_name": "hope", "status": "completed"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.episodic_memory.list_plans.assert_called_once_with("hope", "completed")


@pytest.mark.integration
async def test_check_plans_with_all_searches_unscoped(mock_orchestrator):
    from tools.registry import _make_check_plans_handler

    mock_orchestrator.bundle.episodic_memory.list_plans = MagicMock(return_value=[])
    handler = _make_check_plans_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"agent_name": "all"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.episodic_memory.list_plans.assert_called_once_with(None, "pending")


@pytest.mark.integration
async def test_check_plans_formats_results(mock_orchestrator):
    from tools.registry import _make_check_plans_handler

    matching_plans = [
        SimpleNamespace(agent="atlas", description="clean up the notes folder", status="pending"),
    ]
    mock_orchestrator.bundle.episodic_memory.list_plans = MagicMock(return_value=matching_plans)
    handler = _make_check_plans_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    sent = mock_params.result_callback.call_args[0][0]
    assert "clean up the notes folder" in sent
    assert "pending" in sent


@pytest.mark.integration
async def test_check_plans_with_no_results_returns_friendly_message(mock_orchestrator):
    from tools.registry import _make_check_plans_handler

    mock_orchestrator.bundle.episodic_memory.list_plans = MagicMock(return_value=[])
    handler = _make_check_plans_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"status": "abandoned"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_params.result_callback.assert_called_once_with("No abandoned plans found.")

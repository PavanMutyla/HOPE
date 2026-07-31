"""
Integration tests for the coordination-pool tool handlers
(tools/registry.py::_make_post_task_handler etc.).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from memory.coordination.schema import Signal, Task


def _task(**overrides):
    defaults = dict(
        task_id="task_1", description="clean up notes", owner_agent=None, status="open",
        payload=None, created_by="hope", created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return Task(**defaults)


def _signal(**overrides):
    defaults = dict(
        id="sig_1", from_agent="hope", to_agent="atlas", payload="check the logs",
        created_at="2026-01-01T00:00:00Z", read_at=None,
    )
    defaults.update(overrides)
    return Signal(**defaults)


@pytest.mark.integration
async def test_post_task_uses_caller_agent_as_created_by(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_post_task_handler

    agent_state.active = "hope"
    mock_orchestrator.bundle.blackboard.post_task = MagicMock(return_value="task_1")
    handler = _make_post_task_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"description": "clean up notes"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.blackboard.post_task.assert_called_once_with(
        "clean up notes", "hope"
    )
    mock_params.result_callback.assert_called_once_with("Posted task task_1.")


@pytest.mark.integration
async def test_claim_task_success_reports_claimed(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_claim_task_handler

    agent_state.active = "atlas"
    mock_orchestrator.bundle.blackboard.claim_task = MagicMock(return_value=True)
    handler = _make_claim_task_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"task_id": "task_1"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.blackboard.claim_task.assert_called_once_with("task_1", "atlas")
    mock_params.result_callback.assert_called_once_with("Claimed task task_1.")


@pytest.mark.integration
async def test_claim_task_failure_reports_could_not_claim(mock_orchestrator):
    from tools.registry import _make_claim_task_handler

    mock_orchestrator.bundle.blackboard.claim_task = MagicMock(return_value=False)
    handler = _make_claim_task_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"task_id": "task_1"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    [message] = mock_params.result_callback.call_args[0]
    assert "task_1" in message
    assert "Claimed" not in message


@pytest.mark.integration
async def test_update_task_status_success_reports_new_status(mock_orchestrator):
    from tools.registry import _make_update_task_status_handler

    mock_orchestrator.bundle.blackboard.update_task_status = MagicMock(return_value=True)
    handler = _make_update_task_status_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"task_id": "task_1", "status": "completed", "detail": "all done"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.blackboard.update_task_status.assert_called_once_with(
        "task_1", "completed", "all done"
    )
    mock_params.result_callback.assert_called_once_with("Task task_1 marked completed.")


@pytest.mark.integration
async def test_update_task_status_missing_task_reports_not_found(mock_orchestrator):
    from tools.registry import _make_update_task_status_handler

    mock_orchestrator.bundle.blackboard.update_task_status = MagicMock(return_value=False)
    handler = _make_update_task_status_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"task_id": "task_1", "status": "completed"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_params.result_callback.assert_called_once_with("No task found with id task_1.")


@pytest.mark.integration
async def test_get_active_tasks_defaults_to_every_agent(mock_orchestrator):
    from tools.registry import _make_get_active_tasks_handler

    mock_orchestrator.bundle.blackboard.get_active_tasks = MagicMock(return_value=[])
    handler = _make_get_active_tasks_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.blackboard.get_active_tasks.assert_called_once_with(None)
    mock_params.result_callback.assert_called_once_with("No active tasks found.")


@pytest.mark.integration
async def test_get_active_tasks_with_results_lists_them(mock_orchestrator):
    from tools.registry import _make_get_active_tasks_handler

    mock_orchestrator.bundle.blackboard.get_active_tasks = MagicMock(
        return_value=[_task(task_id="task_1", owner_agent="atlas", status="claimed")]
    )
    handler = _make_get_active_tasks_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"agent_name": "atlas"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.blackboard.get_active_tasks.assert_called_once_with("atlas")
    [message] = mock_params.result_callback.call_args[0]
    assert "task_1" in message
    assert "atlas" in message


@pytest.mark.integration
async def test_send_signal_uses_caller_agent_as_from_agent(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_send_signal_handler

    agent_state.active = "hope"
    mock_orchestrator.bundle.blackboard.send_signal = MagicMock(return_value="sig_1")
    handler = _make_send_signal_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"to_agent": "atlas", "payload": "check the logs"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.blackboard.send_signal.assert_called_once_with(
        "hope", "atlas", "check the logs"
    )
    mock_params.result_callback.assert_called_once_with("Sent signal sig_1 to atlas.")


@pytest.mark.integration
async def test_get_signals_defaults_to_own_agent(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_get_signals_handler

    agent_state.active = "atlas"
    mock_orchestrator.bundle.blackboard.get_signals_for = MagicMock(return_value=[])
    handler = _make_get_signals_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.blackboard.get_signals_for.assert_called_once_with("atlas")
    mock_params.result_callback.assert_called_once_with("No unread signals.")


@pytest.mark.integration
async def test_get_signals_with_results_lists_them(mock_orchestrator):
    from tools.registry import _make_get_signals_handler

    mock_orchestrator.bundle.blackboard.get_signals_for = MagicMock(
        return_value=[_signal(from_agent="hope", payload="check the logs")]
    )
    handler = _make_get_signals_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"agent_name": "atlas"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.blackboard.get_signals_for.assert_called_once_with("atlas")
    [message] = mock_params.result_callback.call_args[0]
    assert "hope" in message
    assert "check the logs" in message

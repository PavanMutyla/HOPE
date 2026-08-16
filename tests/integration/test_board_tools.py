"""
Integration tests for the shared-board tool handlers
(tools/registry.py::_make_add_task_handler etc.).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from memory.board.schema import BoardItem, QuickNote


def _item(**overrides):
    defaults = dict(
        id=1, list_type="today", text="buy milk", done=False, agent="hope",
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return BoardItem(**defaults)


def _note(**overrides):
    defaults = dict(content="call the dentist", agent="hope", updated_at="2026-01-01T00:00:00Z")
    defaults.update(overrides)
    return QuickNote(**defaults)


@pytest.mark.integration
async def test_add_task_uses_caller_agent(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_add_task_handler

    agent_state.active = "hope"
    mock_orchestrator.bundle.board.add_item = MagicMock(return_value=_item())
    handler = _make_add_task_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"list_type": "today", "text": "buy milk"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.board.add_item.assert_called_once_with("today", "buy milk", "hope")
    [message] = mock_params.result_callback.call_args[0]
    assert "buy milk" in message


@pytest.mark.integration
async def test_update_task_success_reports_new_text(mock_orchestrator):
    from tools.registry import _make_update_task_handler

    mock_orchestrator.bundle.board.update_item_text = MagicMock(
        return_value=_item(text="buy oat milk")
    )
    handler = _make_update_task_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"item_id": 1, "text": "buy oat milk"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    [message] = mock_params.result_callback.call_args[0]
    assert "buy oat milk" in message


@pytest.mark.integration
async def test_update_task_missing_id_reports_not_found(mock_orchestrator):
    from tools.registry import _make_update_task_handler

    mock_orchestrator.bundle.board.update_item_text = MagicMock(return_value=None)
    handler = _make_update_task_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"item_id": 999, "text": "x"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_params.result_callback.assert_called_once_with("No task found with id 999.")


@pytest.mark.integration
async def test_toggle_task_reports_done_state(mock_orchestrator):
    from tools.registry import _make_toggle_task_handler

    mock_orchestrator.bundle.board.toggle_item = MagicMock(return_value=_item(done=True))
    handler = _make_toggle_task_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"item_id": 1}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_params.result_callback.assert_called_once_with("Task 1 is now done.")


@pytest.mark.integration
async def test_delete_task_success_reports_deleted(mock_orchestrator):
    from tools.registry import _make_delete_task_handler

    mock_orchestrator.bundle.board.delete_item = MagicMock(return_value=True)
    handler = _make_delete_task_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"item_id": 1}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_params.result_callback.assert_called_once_with("Deleted task 1.")


@pytest.mark.integration
async def test_get_tasks_empty_list_reports_nothing(mock_orchestrator):
    from tools.registry import _make_get_tasks_handler

    mock_orchestrator.bundle.board.list_items = MagicMock(return_value=[])
    handler = _make_get_tasks_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"list_type": "pending"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.board.list_items.assert_called_once_with("pending")
    mock_params.result_callback.assert_called_once_with("Nothing on the pending list.")


@pytest.mark.integration
async def test_get_tasks_with_results_lists_them(mock_orchestrator):
    from tools.registry import _make_get_tasks_handler

    mock_orchestrator.bundle.board.list_items = MagicMock(return_value=[_item()])
    handler = _make_get_tasks_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"list_type": "today"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    [message] = mock_params.result_callback.call_args[0]
    assert "buy milk" in message
    assert "hope" in message


@pytest.mark.integration
async def test_get_quick_note_empty_reports_empty(mock_orchestrator):
    from tools.registry import _make_get_quick_note_handler

    mock_orchestrator.bundle.board.get_quick_note = MagicMock(
        return_value=_note(content="")
    )
    handler = _make_get_quick_note_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_params.result_callback.assert_called_once_with("Quick notes is empty.")


@pytest.mark.integration
async def test_update_quick_note_uses_caller_agent(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_update_quick_note_handler

    agent_state.active = "atlas"
    mock_orchestrator.bundle.board.update_quick_note = MagicMock(return_value=_note())
    handler = _make_update_quick_note_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"content": "new content"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.board.update_quick_note.assert_called_once_with(
        "new content", "atlas"
    )


@pytest.mark.integration
async def test_get_location_and_time_reports_city(monkeypatch):
    import tools.registry as registry

    monkeypatch.setattr(
        registry.board_live,
        "get_location_and_time",
        AsyncMock(return_value={
            "city": "Austin, TX", "lat": 30.27, "lon": -97.74,
            "local_time": "3:42 PM", "local_date": "Monday, August 17",
        }),
    )

    mock_params = MagicMock()
    mock_params.arguments = {}
    mock_params.result_callback = AsyncMock()
    await registry.get_location_and_time_handler(mock_params)

    [message] = mock_params.result_callback.call_args[0]
    assert "Austin, TX" in message


@pytest.mark.integration
async def test_get_weather_reports_temperature(monkeypatch):
    import tools.registry as registry

    monkeypatch.setattr(
        registry.board_live,
        "get_weather",
        AsyncMock(return_value={
            "temp_c": 27, "condition": "Partly Cloudy", "hi_c": 31, "lo_c": 22, "wind_kmh": 10,
        }),
    )

    mock_params = MagicMock()
    mock_params.arguments = {}
    mock_params.result_callback = AsyncMock()
    await registry.get_weather_handler(mock_params)

    [message] = mock_params.result_callback.call_args[0]
    assert "27" in message
    assert "Partly Cloudy" in message

"""
Integration tests for the procedural-memory tool handlers
(tools/registry.py::_make_save_procedure_handler /
_make_recall_procedure_handler / _make_record_procedure_outcome_handler).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.integration
async def test_save_procedure_saves_under_the_active_agent(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_save_procedure_handler

    agent_state.active = "atlas"
    saved = SimpleNamespace(name="restart-audio", steps=["a", "b"])
    mock_orchestrator.bundle.procedural_memory.save = MagicMock(return_value=saved)
    handler = _make_save_procedure_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {
        "name": "restart audio",
        "description": "when audio hangs",
        "steps": ["a", "b"],
    }
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.procedural_memory.save.assert_called_once_with(
        "atlas", "restart audio", "when audio hangs", ["a", "b"]
    )
    mock_params.result_callback.assert_called_once_with(
        "Saved procedure 'restart-audio' with 2 steps."
    )


@pytest.mark.integration
async def test_save_procedure_surfaces_duplicate_error_instead_of_raising(mock_orchestrator):
    from tools.registry import _make_save_procedure_handler

    mock_orchestrator.bundle.procedural_memory.save = MagicMock(
        side_effect=ValueError("already exists and is active")
    )
    handler = _make_save_procedure_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"name": "x", "description": "y", "steps": ["z"]}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)  # must not raise

    mock_params.result_callback.assert_called_once_with("already exists and is active")


@pytest.mark.integration
async def test_recall_procedure_defaults_to_own_agent(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_recall_procedure_handler

    agent_state.active = "atlas"
    mock_orchestrator.bundle.procedural_memory.recall = MagicMock(return_value=[])
    handler = _make_recall_procedure_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "restart audio"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.procedural_memory.recall.assert_called_once_with(
        "restart audio", "atlas", 3
    )


@pytest.mark.integration
async def test_recall_procedure_with_explicit_agent_name_scopes_to_that_agent(mock_orchestrator):
    from tools.registry import _make_recall_procedure_handler

    mock_orchestrator.bundle.procedural_memory.recall = MagicMock(return_value=[])
    handler = _make_recall_procedure_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "greet the user", "agent_name": "hope"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.procedural_memory.recall.assert_called_once_with(
        "greet the user", "hope", 3
    )


@pytest.mark.integration
async def test_recall_procedure_formats_results_with_trust_counts(mock_orchestrator):
    from tools.registry import _make_recall_procedure_handler

    procedures = [
        SimpleNamespace(
            name="restart-audio", description="when audio hangs",
            steps=["check device", "kill process"], success_count=3, failure_count=1,
        ),
    ]
    mock_orchestrator.bundle.procedural_memory.recall = MagicMock(return_value=procedures)
    handler = _make_recall_procedure_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "audio issue"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    sent = mock_params.result_callback.call_args[0][0]
    assert "restart-audio" in sent
    assert "succeeded 3x" in sent
    assert "failed 1x" in sent
    assert "check device -> kill process" in sent


@pytest.mark.integration
async def test_recall_procedure_with_no_results_returns_friendly_message(mock_orchestrator):
    from tools.registry import _make_recall_procedure_handler

    mock_orchestrator.bundle.procedural_memory.recall = MagicMock(return_value=[])
    handler = _make_recall_procedure_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "nothing relevant"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_params.result_callback.assert_called_once_with("No matching procedures found.")


@pytest.mark.integration
async def test_record_procedure_outcome_reports_updated_counts(mock_orchestrator):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_record_procedure_outcome_handler

    agent_state.active = "atlas"
    updated = SimpleNamespace(name="restart-audio", success_count=4, failure_count=1)
    mock_orchestrator.bundle.procedural_memory.record_outcome = MagicMock(return_value=updated)
    handler = _make_record_procedure_outcome_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"name": "restart-audio", "success": True}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.procedural_memory.record_outcome.assert_called_once_with(
        "atlas", "restart-audio", True
    )
    mock_params.result_callback.assert_called_once_with(
        "Recorded. 'restart-audio' has 4 successes and 1 failures so far."
    )


@pytest.mark.integration
async def test_record_procedure_outcome_surfaces_missing_procedure_error(mock_orchestrator):
    from tools.registry import _make_record_procedure_outcome_handler

    mock_orchestrator.bundle.procedural_memory.record_outcome = MagicMock(
        side_effect=ValueError("No procedure 'x' for agent 'atlas'")
    )
    handler = _make_record_procedure_outcome_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"name": "x", "success": False}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)  # must not raise

    mock_params.result_callback.assert_called_once_with("No procedure 'x' for agent 'atlas'")

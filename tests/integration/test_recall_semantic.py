"""
Integration tests for the recall_semantic tool handler — shared-by-default
durable fact retrieval (tools/registry.py::_make_recall_semantic_handler).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.integration
async def test_recall_semantic_defaults_to_shared_pool(mock_orchestrator):
    from tools.registry import _make_recall_semantic_handler

    mock_orchestrator.bundle.semantic_memory.query = MagicMock(return_value=[])
    handler = _make_recall_semantic_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "workspace path"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    # unlike recall_memory, omitting agent_name means "everyone", not "caller's own"
    mock_orchestrator.bundle.semantic_memory.query.assert_called_once_with(
        "workspace path", 5, None
    )


@pytest.mark.integration
async def test_recall_semantic_with_explicit_agent_name_scopes_to_that_agent(mock_orchestrator):
    from tools.registry import _make_recall_semantic_handler

    mock_orchestrator.bundle.semantic_memory.query = MagicMock(return_value=[])
    handler = _make_recall_semantic_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "tool quirks", "agent_name": "atlas"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_orchestrator.bundle.semantic_memory.query.assert_called_once_with(
        "tool quirks", 5, "atlas"
    )


@pytest.mark.integration
async def test_recall_semantic_formats_results_for_callback(mock_orchestrator):
    from tools.registry import _make_recall_semantic_handler

    facts = [
        {"memory": "Pavan's main workspace is /home/pavan/Desktop/Projects/HOPE.", "agent_id": "hope"},
        {"memory": "Atlas should avoid touching .venv/.", "agent_id": "atlas"},
    ]
    mock_orchestrator.bundle.semantic_memory.query = MagicMock(return_value=facts)
    handler = _make_recall_semantic_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "workspace"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    sent = mock_params.result_callback.call_args[0][0]
    assert "Pavan's main workspace is /home/pavan/Desktop/Projects/HOPE." in sent
    assert "Atlas should avoid touching .venv/." in sent


@pytest.mark.integration
async def test_recall_semantic_with_no_results_returns_friendly_message(mock_orchestrator):
    from tools.registry import _make_recall_semantic_handler

    mock_orchestrator.bundle.semantic_memory.query = MagicMock(return_value=[])
    handler = _make_recall_semantic_handler(mock_orchestrator)

    mock_params = MagicMock()
    mock_params.arguments = {"query": "nothing relevant"}
    mock_params.result_callback = AsyncMock()
    await handler(mock_params)

    mock_params.result_callback.assert_called_once_with("No matching facts found.")

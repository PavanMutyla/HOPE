"""
Integration tests for HOPE → Atlas task delegation.

Tests that the delegation handler correctly dispatches tasks to Atlas
and immediately acknowledges the user without blocking.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.integration
async def test_delegation_acknowledges_immediately():
    """Handler must call result_callback synchronously before Atlas finishes."""
    from tools.registry import delegate_to_atlas_handler
    from pipecat.frames.frames import FunctionCallResultProperties

    mock_params = MagicMock()
    mock_params.arguments = {"task": "create a file called test.txt"}
    mock_params.result_callback = AsyncMock()

    with patch("tools.registry.atlas") as mock_atlas:
        mock_atlas.run = AsyncMock()
        await delegate_to_atlas_handler(mock_params)

    mock_params.result_callback.assert_called_once()


@pytest.mark.integration
async def test_delegation_passes_task_to_atlas():
    """Atlas.run must be called with the task string from arguments."""
    from tools.registry import delegate_to_atlas_handler

    mock_params = MagicMock()
    mock_params.arguments = {"task": "list all files in the workspace"}
    mock_params.result_callback = AsyncMock()

    with patch("tools.registry.atlas") as mock_atlas:
        mock_atlas.run = AsyncMock()
        await delegate_to_atlas_handler(mock_params)

    # asyncio.create_task is called with a coroutine — atlas.run must have been invoked
    mock_atlas.run.assert_called_once()
    call_args = mock_atlas.run.call_args[0]
    assert call_args[0] == "list all files in the workspace"


@pytest.mark.integration
async def test_delegation_acknowledgement_is_non_final():
    """
    The immediate acknowledgement uses is_final=False so the pipeline
    keeps the LLM context open for Atlas's eventual result.
    """
    from tools.registry import delegate_to_atlas_handler
    from pipecat.frames.frames import FunctionCallResultProperties

    mock_params = MagicMock()
    mock_params.arguments = {"task": "delete test.txt"}
    mock_params.result_callback = AsyncMock()

    with patch("tools.registry.atlas") as mock_atlas:
        mock_atlas.run = AsyncMock()
        await delegate_to_atlas_handler(mock_params)

    call_kwargs = mock_params.result_callback.call_args.kwargs
    props: FunctionCallResultProperties = call_kwargs.get("properties")
    assert props is not None
    assert props.is_final is False

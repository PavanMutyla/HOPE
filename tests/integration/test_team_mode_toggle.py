"""
Integration tests for the enable_team_mode / disable_team_mode tool handlers
(tools/registry.py::enable_team_mode_handler, disable_team_mode_handler).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.voice.team_state import team_state


@pytest.fixture(autouse=True)
def reset_team_state(monkeypatch):
    monkeypatch.setattr(team_state, "enabled", False)


@pytest.mark.integration
async def test_enable_team_mode_sets_team_state_enabled():
    from tools.registry import enable_team_mode_handler

    mock_params = MagicMock()
    mock_params.arguments = {}
    mock_params.result_callback = AsyncMock()

    await enable_team_mode_handler(mock_params)

    assert team_state.enabled is True
    mock_params.result_callback.assert_called_once()


@pytest.mark.integration
async def test_disable_team_mode_sets_team_state_disabled(monkeypatch):
    from tools.registry import disable_team_mode_handler

    monkeypatch.setattr(team_state, "enabled", True)
    mock_params = MagicMock()
    mock_params.arguments = {}
    mock_params.result_callback = AsyncMock()

    await disable_team_mode_handler(mock_params)

    assert team_state.enabled is False
    mock_params.result_callback.assert_called_once()

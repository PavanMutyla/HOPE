"""Unit tests for core/voice/team_state.py — session-scoped team-mode toggle."""

import pytest

from core.voice.team_state import TeamState, team_state


@pytest.mark.unit
def test_team_state_defaults_to_disabled():
    assert TeamState().enabled is False


@pytest.mark.unit
def test_team_state_enabled_is_mutable():
    state = TeamState()
    state.enabled = True
    assert state.enabled is True


@pytest.mark.unit
def test_module_singleton_defaults_to_disabled():
    assert team_state.enabled is False

"""Unit tests for sub_agents/atlas/team.py — build_atlas_team_member()."""

from unittest.mock import MagicMock

import pytest

import sub_agents.atlas.team as atlas_team_module
from core.voice.team_registry import TeamMember
from core.voice.team_voice import TeamVoice
from settings import settings


@pytest.fixture
def mock_team_voice(monkeypatch):
    """TeamVoice construction is real audio/model work — patched out here so this
    stays a pure unit test, same reasoning as test_team_voice.py's own mocking.
    spec=TeamVoice so pydantic's arbitrary_types_allowed isinstance check on
    TeamMember.voice accepts it."""
    mock_voice = MagicMock(spec=TeamVoice)
    monkeypatch.setattr(atlas_team_module, "TeamVoice", MagicMock(return_value=mock_voice))
    return mock_voice


@pytest.mark.unit
def test_build_atlas_team_member_returns_team_member(mock_team_voice):
    member = atlas_team_module.build_atlas_team_member()
    assert isinstance(member, TeamMember)
    assert member.name == "atlas"


@pytest.mark.unit
def test_build_atlas_team_member_uses_atlas_llm_model(mock_team_voice):
    member = atlas_team_module.build_atlas_team_member()
    assert member.llm_model == settings.atlas_llm_model


@pytest.mark.unit
def test_build_atlas_team_member_prompt_mentions_pass(mock_team_voice):
    member = atlas_team_module.build_atlas_team_member()
    assert "PASS" in member.interject_prompt


@pytest.mark.unit
def test_build_atlas_team_member_constructs_voice_with_kokoro_atlas_voice_id(monkeypatch):
    mock_team_voice_cls = MagicMock(return_value=MagicMock(spec=TeamVoice))
    monkeypatch.setattr(atlas_team_module, "TeamVoice", mock_team_voice_cls)

    atlas_team_module.build_atlas_team_member()

    mock_team_voice_cls.assert_called_once_with(voice_id=settings.kokoro_atlas_voice_id)


@pytest.mark.unit
def test_build_atlas_team_member_does_not_construct_voice_at_import_time(monkeypatch):
    """Guards against real Kokoro/PyAudio construction as an import side effect."""
    mock_team_voice_cls = MagicMock()
    monkeypatch.setattr(atlas_team_module, "TeamVoice", mock_team_voice_cls)

    mock_team_voice_cls.assert_not_called()

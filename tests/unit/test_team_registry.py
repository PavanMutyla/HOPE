"""Unit tests for core/voice/team_registry.py — TeamMember + TeamRegistry."""

from unittest.mock import MagicMock

import pytest

from core.voice.team_registry import TeamMember, TeamRegistry
from core.voice.team_voice import TeamVoice


def _make_member(name: str) -> TeamMember:
    return TeamMember(
        name=name,
        interject_prompt=f"You are {name}, overhearing HOPE's conversation.",
        llm_model="gpt-4o-mini",
        voice=MagicMock(spec=TeamVoice),
    )


@pytest.mark.unit
def test_all_returns_empty_list_when_nothing_registered():
    registry = TeamRegistry()
    assert registry.all() == []


@pytest.mark.unit
def test_register_makes_member_appear_in_all():
    registry = TeamRegistry()
    member = _make_member("atlas")

    registry.register(member)

    assert registry.all() == [member]


@pytest.mark.unit
def test_register_multiple_members():
    registry = TeamRegistry()
    atlas = _make_member("atlas")
    scout = _make_member("scout")

    registry.register(atlas)
    registry.register(scout)

    names = {m.name for m in registry.all()}
    assert names == {"atlas", "scout"}


@pytest.mark.unit
def test_registering_same_name_twice_overwrites():
    registry = TeamRegistry()
    first = _make_member("atlas")
    second = _make_member("atlas")

    registry.register(first)
    registry.register(second)

    assert registry.all() == [second]


@pytest.mark.unit
def test_team_member_rejects_non_team_voice_object():
    with pytest.raises(Exception):
        TeamMember(
            name="atlas",
            interject_prompt="...",
            llm_model="gpt-4o-mini",
            voice="not a TeamVoice",
        )

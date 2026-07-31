"""Unit tests for system prompts — identity, constraints, and interpolation."""

import pytest
from core.prompt import SYSTEM_PROMPT


@pytest.mark.unit
def test_hope_prompt_is_nonempty_string():
    assert isinstance(SYSTEM_PROMPT, str)
    assert len(SYSTEM_PROMPT) > 0


@pytest.mark.unit
def test_hope_prompt_contains_identity():
    assert "HOPE" in SYSTEM_PROMPT


@pytest.mark.unit
def test_hope_prompt_addresses_pavan_by_name():
    assert "Pavan" in SYSTEM_PROMPT


@pytest.mark.unit
def test_hope_prompt_prohibits_markdown():
    lower = SYSTEM_PROMPT.lower()
    assert "markdown" in lower or "bullet" in lower or "no headers" in lower


@pytest.mark.unit
def test_hope_prompt_enforces_voice_first_brevity():
    lower = SYSTEM_PROMPT.lower()
    assert "sentence" in lower or "brief" in lower or "short" in lower


@pytest.mark.unit
def test_hope_prompt_defines_honesty_rules():
    lower = SYSTEM_PROMPT.lower()
    assert "wrong" in lower or "honest" in lower or "uncertain" in lower


@pytest.mark.unit
def test_hope_prompt_length_is_within_context_bounds():
    assert len(SYSTEM_PROMPT) < 16_000, (
        "System prompt exceeds 16,000 chars — risk of context overflow."
    )


@pytest.mark.unit
def test_hope_prompt_mentions_atlas():
    assert "Atlas" in SYSTEM_PROMPT


@pytest.mark.unit
def test_hope_prompt_mentions_team_mode_tools():
    assert "enable_team_mode" in SYSTEM_PROMPT
    assert "disable_team_mode" in SYSTEM_PROMPT


@pytest.mark.unit
def test_hope_prompt_interpolates_atlas_workspace():
    """atlas_workspace from settings must appear in the prompt (f-string interpolation)."""
    from settings import settings
    assert settings.atlas_workspace in SYSTEM_PROMPT


# ─── Atlas prompts ───────────────────────────────────────────────

@pytest.mark.unit
def test_atlas_background_prompt_is_nonempty():
    from sub_agents.atlas.prompt import ATLAS_PROMPT
    assert isinstance(ATLAS_PROMPT, str)
    assert len(ATLAS_PROMPT) > 0


@pytest.mark.unit
def test_atlas_voice_prompt_is_nonempty():
    from sub_agents.atlas.voice_prompt import ATLAS_VOICE_PROMPT
    assert isinstance(ATLAS_VOICE_PROMPT, str)
    assert len(ATLAS_VOICE_PROMPT) > 0


@pytest.mark.unit
def test_atlas_voice_prompt_contains_identity():
    from sub_agents.atlas.voice_prompt import ATLAS_VOICE_PROMPT
    assert "Atlas" in ATLAS_VOICE_PROMPT


@pytest.mark.unit
def test_atlas_voice_prompt_mentions_workspace():
    from sub_agents.atlas.voice_prompt import ATLAS_VOICE_PROMPT
    from settings import settings
    assert settings.atlas_workspace in ATLAS_VOICE_PROMPT


@pytest.mark.unit
def test_atlas_voice_prompt_instructs_handback():
    from sub_agents.atlas.voice_prompt import ATLAS_VOICE_PROMPT
    lower = ATLAS_VOICE_PROMPT.lower()
    assert "handback" in lower or "hope" in lower

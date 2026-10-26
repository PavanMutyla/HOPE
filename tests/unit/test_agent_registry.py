"""Unit tests for VoiceAgent dataclass and AgentRegistry."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.voice.agent import AgentRegistry, VoiceAgent


@pytest.mark.unit
def test_voice_agent_stores_fields():
    agent = VoiceAgent(name="hope", system_prompt="You are HOPE.", voice_id="v1")
    assert agent.name == "hope"
    assert agent.system_prompt == "You are HOPE."
    assert agent.voice_id == "v1"
    assert agent.tools == []


@pytest.mark.unit
def test_register_and_get(hope_voice_agent):
    registry = AgentRegistry()
    registry.register(hope_voice_agent)
    assert registry.get("hope") is hope_voice_agent


@pytest.mark.unit
def test_get_unknown_raises_key_error():
    registry = AgentRegistry()
    with pytest.raises(KeyError, match="hope"):
        registry.get("hope")


@pytest.mark.unit
def test_all_returns_all_registered(hope_voice_agent, atlas_voice_agent):
    registry = AgentRegistry()
    registry.register(hope_voice_agent)
    registry.register(atlas_voice_agent)
    assert {a.name for a in registry.all()} == {"hope", "atlas"}


@pytest.mark.unit
def test_register_overwrites_same_name(hope_voice_agent):
    registry = AgentRegistry()
    registry.register(hope_voice_agent)
    updated = VoiceAgent(name="hope", system_prompt="Updated.", voice_id="v2")
    registry.register(updated)
    assert registry.get("hope").system_prompt == "Updated."


@pytest.mark.unit
async def test_switch_updates_system_prompt(agent_registry):
    context = MagicMock()
    context.messages = [{"role": "system", "content": "You are HOPE."}]
    llm = AsyncMock()

    await agent_registry.switch("atlas", context, llm)

    updated = context.set_messages.call_args[0][0]
    assert updated[0]["content"] == "You are Atlas."


@pytest.mark.unit
async def test_switch_pushes_tts_frame(agent_registry):
    from pipecat.frames.frames import TTSUpdateSettingsFrame

    context = MagicMock()
    context.messages = [{"role": "system", "content": "You are HOPE."}]
    llm = AsyncMock()

    await agent_registry.switch("atlas", context, llm)

    llm.push_frame.assert_called_once()
    assert isinstance(llm.push_frame.call_args[0][0], TTSUpdateSettingsFrame)


@pytest.mark.unit
async def test_switch_tts_frame_carries_kokoro_settings(agent_registry):
    from pipecat.frames.frames import TTSUpdateSettingsFrame
    from pipecat.services.kokoro.tts import KokoroTTSSettings

    context = MagicMock()
    context.messages = [{"role": "system", "content": "You are HOPE."}]
    llm = AsyncMock()

    await agent_registry.switch("atlas", context, llm)

    frame = llm.push_frame.call_args[0][0]
    assert isinstance(frame, TTSUpdateSettingsFrame)
    assert isinstance(frame.delta, KokoroTTSSettings)


@pytest.mark.unit
async def test_switch_tts_frame_carries_target_voice_id(agent_registry):
    context = MagicMock()
    context.messages = [{"role": "system", "content": "You are HOPE."}]
    llm = AsyncMock()

    await agent_registry.switch("atlas", context, llm)

    frame = llm.push_frame.call_args[0][0]
    assert frame.delta.voice == "atlas-v2"


@pytest.mark.unit
async def test_switch_updates_agent_state(agent_registry):
    from core.voice.agent_state import agent_state

    context = MagicMock()
    context.messages = [{"role": "system", "content": "You are HOPE."}]
    llm = AsyncMock()
    agent_state.active = "hope"

    await agent_registry.switch("atlas", context, llm)

    assert agent_state.active == "atlas"


@pytest.mark.unit
async def test_switch_to_unknown_agent_raises(agent_registry):
    context = MagicMock()
    context.messages = [{"role": "system", "content": "You are HOPE."}]
    llm = AsyncMock()

    with pytest.raises(KeyError):
        await agent_registry.switch("nonexistent", context, llm)


@pytest.mark.unit
def test_unregister_removes_agent(agent_registry):
    agent_registry.unregister("atlas")
    with pytest.raises(KeyError):
        agent_registry.get("atlas")


@pytest.mark.unit
def test_unregister_unknown_agent_is_a_no_op(agent_registry):
    agent_registry.unregister("nobody")
    assert len(agent_registry.all()) == 2


@pytest.mark.unit
def test_find_matches_spoken_name_case_insensitively(agent_registry):
    from core.voice.agent import VoiceAgent

    emma = VoiceAgent(name="emma", system_prompt="", voice_id="bf_emma", spoken_name="Emma")
    agent_registry.register(emma)
    assert agent_registry.find("Emma") is emma
    assert agent_registry.find("  EMMA ") is emma


@pytest.mark.unit
def test_find_matches_registry_name(agent_registry, atlas_voice_agent):
    assert agent_registry.find("Atlas") is atlas_voice_agent


@pytest.mark.unit
def test_find_unknown_returns_none(agent_registry):
    assert agent_registry.find("nobody") is None


@pytest.mark.unit
def test_current_prompt_defaults_to_system_prompt(atlas_voice_agent):
    assert atlas_voice_agent.current_prompt() == "You are Atlas."


@pytest.mark.unit
async def test_switch_uses_prompt_provider_at_switch_time(agent_registry):
    from core.voice.agent import VoiceAgent

    state = {"findings": "nothing yet"}
    emma = VoiceAgent(
        name="emma", system_prompt="", voice_id="bf_emma", spoken_name="Emma",
        prompt_provider=lambda: f"Findings: {state['findings']}",
    )
    agent_registry.register(emma)
    state["findings"] = "54 voices"  # changes after registration

    context = MagicMock()
    context.messages = [{"role": "system", "content": "You are HOPE."}]
    await agent_registry.switch("emma", context, AsyncMock())

    assert context.set_messages.call_args[0][0][0]["content"] == "Findings: 54 voices"

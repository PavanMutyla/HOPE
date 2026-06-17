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

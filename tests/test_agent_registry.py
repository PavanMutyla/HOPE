from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agent import AgentRegistry, VoiceAgent


@pytest.fixture
def hope_agent():
    return VoiceAgent(name="hope", system_prompt="You are HOPE.", voice_id="hope-v1")


@pytest.fixture
def atlas_agent():
    return VoiceAgent(name="atlas", system_prompt="You are Atlas.", voice_id="atlas-v2")


def test_register_and_get(hope_agent):
    registry = AgentRegistry()
    registry.register(hope_agent)
    assert registry.get("hope") is hope_agent


def test_get_unknown_raises():
    registry = AgentRegistry()
    with pytest.raises(KeyError, match="hope"):
        registry.get("hope")


def test_all_returns_registered_names(hope_agent, atlas_agent):
    registry = AgentRegistry()
    registry.register(hope_agent)
    registry.register(atlas_agent)
    assert {a.name for a in registry.all()} == {"hope", "atlas"}


async def test_switch_updates_system_prompt(hope_agent, atlas_agent):
    registry = AgentRegistry()
    registry.register(hope_agent)
    registry.register(atlas_agent)
    context = MagicMock()
    context.messages = [{"role": "system", "content": "You are HOPE."}]
    llm = AsyncMock()

    await registry.switch("atlas", context, llm)

    updated = context.set_messages.call_args[0][0]
    assert updated[0]["content"] == "You are Atlas."


async def test_switch_pushes_tts_frame(hope_agent, atlas_agent):
    registry = AgentRegistry()
    registry.register(hope_agent)
    registry.register(atlas_agent)
    context = MagicMock()
    context.messages = [{"role": "system", "content": "You are HOPE."}]
    llm = AsyncMock()

    await registry.switch("atlas", context, llm)

    llm.push_frame.assert_called_once()
    from pipecat.frames.frames import TTSUpdateSettingsFrame
    assert isinstance(llm.push_frame.call_args[0][0], TTSUpdateSettingsFrame)


async def test_switch_updates_agent_state(hope_agent, atlas_agent):
    registry = AgentRegistry()
    registry.register(hope_agent)
    registry.register(atlas_agent)
    context = MagicMock()
    context.messages = [{"role": "system", "content": "You are HOPE."}]
    llm = AsyncMock()
    from core.agent_state import agent_state
    agent_state.active = "hope"

    await registry.switch("atlas", context, llm)

    assert agent_state.active == "atlas"

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agent import AgentRegistry, VoiceAgent
from core.orchestrator import VoiceOrchestrator


@pytest.fixture
def registry():
    r = AgentRegistry()
    r.register(VoiceAgent(name="hope", system_prompt="You are HOPE.", voice_id="v1"))
    r.register(VoiceAgent(name="atlas", system_prompt="You are Atlas.", voice_id="v2"))
    return r


async def test_agent_to_agent_uses_target_system_prompt(registry):
    bundle = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "I see 3 files."

    with patch("core.orchestrator.AsyncOpenAI") as MockOpenAI:
        mock_client = AsyncMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        orchestrator = VoiceOrchestrator(registry, bundle)
        result = await orchestrator.agent_to_agent("hope", "atlas", "What's in the workspace?")

    assert result == "I see 3 files."
    messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    assert messages[0]["content"] == "You are Atlas."
    assert "What's in the workspace?" in messages[1]["content"]
    assert "hope" in messages[1]["content"]


async def test_agent_to_agent_returns_empty_string_on_none(registry):
    bundle = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = None

    with patch("core.orchestrator.AsyncOpenAI") as MockOpenAI:
        mock_client = AsyncMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        orchestrator = VoiceOrchestrator(registry, bundle)
        result = await orchestrator.agent_to_agent("hope", "atlas", "hello")

    assert result == ""


async def test_switch_to_delegates_to_registry(registry):
    bundle = MagicMock()
    bundle.context = MagicMock()
    bundle.context.messages = [{"role": "system", "content": "You are HOPE."}]
    bundle.llm = AsyncMock()

    with patch("core.orchestrator.AsyncOpenAI"):
        orchestrator = VoiceOrchestrator(registry, bundle)
        await orchestrator.switch_to("atlas")

    bundle.llm.push_frame.assert_called_once()
    updated = bundle.context.set_messages.call_args[0][0]
    assert updated[0]["content"] == "You are Atlas."

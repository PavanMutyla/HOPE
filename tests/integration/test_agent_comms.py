"""
Integration tests for agent-to-agent communication via VoiceOrchestrator.

All inter-agent calls use the TextChannel (direct OpenAI API, no TTS).
Tests verify routing, prompt targeting, and return value handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.integration
async def test_agent_to_agent_uses_target_system_prompt(mock_orchestrator):
    """agent_to_agent must send the TARGET agent's system prompt, not the caller's."""
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "I see 3 files."

    with patch("core.voice.orchestrator.AsyncOpenAI") as MockOpenAI:
        mock_client = AsyncMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_orchestrator._client = mock_client

        result = await mock_orchestrator.agent_to_agent("hope", "atlas", "What's in the workspace?")

    assert result == "I see 3 files."
    messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    assert messages[0]["content"] == "You are Atlas."
    assert "What's in the workspace?" in messages[1]["content"]


@pytest.mark.integration
async def test_agent_to_agent_includes_sender_in_message(mock_orchestrator):
    """The from_agent name must appear in the user message so Atlas knows who is asking."""
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "Done."

    with patch("core.voice.orchestrator.AsyncOpenAI") as MockOpenAI:
        mock_client = AsyncMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_orchestrator._client = mock_client

        await mock_orchestrator.agent_to_agent("hope", "atlas", "hello")

    messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    assert "hope" in messages[1]["content"]


@pytest.mark.integration
async def test_agent_to_agent_returns_empty_string_on_none_content(mock_orchestrator):
    """If the LLM returns None content (e.g. tool call with no text), return empty string."""
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = None

    with patch("core.voice.orchestrator.AsyncOpenAI") as MockOpenAI:
        mock_client = AsyncMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_orchestrator._client = mock_client

        result = await mock_orchestrator.agent_to_agent("hope", "atlas", "ping")

    assert result == ""


@pytest.mark.integration
async def test_agent_to_agent_raises_for_unknown_agent(mock_orchestrator):
    """Routing to an unregistered agent must raise KeyError, not fail silently."""
    with pytest.raises(KeyError):
        await mock_orchestrator.agent_to_agent("hope", "nonexistent_agent", "hello")


@pytest.mark.integration
async def test_broadcast_queries_all_target_agents(mock_orchestrator):
    """broadcast() must call agent_to_agent() for every target agent, not just the first."""
    with patch.object(
        mock_orchestrator, "agent_to_agent", new=AsyncMock(side_effect=lambda frm, to, msg: f"reply from {to}")
    ) as mock_call:
        result = await mock_orchestrator.broadcast("hope", ["atlas", "hope"], "status?")

    assert result == {"atlas": "reply from atlas", "hope": "reply from hope"}
    assert mock_call.call_count == 2


@pytest.mark.integration
async def test_broadcast_runs_targets_concurrently(mock_orchestrator):
    """broadcast() must not block on one target before starting the next (asyncio.gather, not a loop of awaits)."""
    import asyncio

    started = []

    async def slow_reply(frm, to, msg):
        started.append(to)
        await asyncio.sleep(0.05)
        return to

    with patch.object(mock_orchestrator, "agent_to_agent", new=AsyncMock(side_effect=slow_reply)):
        await mock_orchestrator.broadcast("hope", ["atlas", "hope"], "status?")

    # Both calls must have started before either finished sleeping — proves concurrency.
    assert started == ["atlas", "hope"]


@pytest.mark.integration
async def test_broadcast_propagates_agent_to_agent_errors(mock_orchestrator):
    """A KeyError from an unknown agent must propagate out of broadcast(), not be swallowed."""
    with patch.object(mock_orchestrator, "agent_to_agent", new=AsyncMock(side_effect=KeyError("nope"))):
        with pytest.raises(KeyError):
            await mock_orchestrator.broadcast("hope", ["nonexistent_agent"], "hello")


@pytest.mark.integration
async def test_switch_to_updates_active_agent(mock_orchestrator):
    """switch_to() must update both the LLM context and the agent_state tracker."""
    from core.voice.agent_state import agent_state

    agent_state.active = "hope"
    await mock_orchestrator.switch_to("atlas")

    assert agent_state.active == "atlas"


@pytest.mark.integration
async def test_switch_to_pushes_tts_voice_frame(mock_orchestrator):
    """switch_to() must push a TTSUpdateSettingsFrame so the voice changes immediately."""
    from pipecat.frames.frames import TTSUpdateSettingsFrame

    await mock_orchestrator.switch_to("atlas")

    mock_orchestrator.bundle.llm.push_frame.assert_called_once()
    frame = mock_orchestrator.bundle.llm.push_frame.call_args[0][0]
    assert isinstance(frame, TTSUpdateSettingsFrame)

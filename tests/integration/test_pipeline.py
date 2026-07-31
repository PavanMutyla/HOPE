"""
Integration tests for build_pipeline() — verifies wiring without hardware or API calls.

All external service constructors are patched by the `pipeline_mocks` fixture so this
suite runs with zero credentials and no audio device.
"""

import pytest
from core.voice.agent import VoiceAgent
from core.voice.pipeline import VoicePipelineBundle


@pytest.mark.integration
def test_build_pipeline_returns_voice_pipeline_bundle(pipeline_mocks):
    from core.voice.pipeline import build_pipeline

    agent = VoiceAgent(name="hope", system_prompt="You are HOPE.", voice_id="test-v1")
    bundle = build_pipeline(agent, [])

    assert isinstance(bundle, VoicePipelineBundle)


@pytest.mark.integration
def test_bundle_exposes_all_required_fields(pipeline_mocks):
    from core.voice.pipeline import build_pipeline

    agent = VoiceAgent(name="hope", system_prompt="You are HOPE.", voice_id="test-v1")
    bundle = build_pipeline(agent, [])

    assert bundle.pipeline is not None
    assert bundle.worker is not None
    assert bundle.llm is not None
    assert bundle.tts is not None
    assert bundle.context is not None
    assert bundle.transport is not None
    assert bundle.panel is not None
    assert bundle.tracer is not None
    assert bundle.episodic_memory is not None
    assert bundle.semantic_memory is not None
    assert bundle.procedural_memory is not None
    assert bundle.blackboard is not None


@pytest.mark.integration
def test_tts_initialized_with_agent_voice_id(pipeline_mocks):
    from core.voice.pipeline import build_pipeline

    agent = VoiceAgent(name="hope", system_prompt="You are HOPE.", voice_id="my-special-voice")
    build_pipeline(agent, [])

    mock_tts_cls = pipeline_mocks["KokoroTTSService"]
    assert mock_tts_cls.called
    mock_tts_cls.Settings.assert_called_once_with(voice="my-special-voice")


@pytest.mark.integration
def test_context_initialized_with_agent_system_prompt(pipeline_mocks):
    from core.voice.pipeline import build_pipeline

    agent = VoiceAgent(name="hope", system_prompt="Custom system prompt.", voice_id="v1")
    bundle = build_pipeline(agent, [])

    # LLMContext is NOT mocked — we read the real context object
    assert bundle.context.messages[0]["content"] == "Custom system prompt."


@pytest.mark.integration
def test_llm_service_is_constructed(pipeline_mocks):
    from core.voice.pipeline import build_pipeline

    agent = VoiceAgent(name="hope", system_prompt="test", voice_id="v1")
    build_pipeline(agent, [])

    assert pipeline_mocks["OpenAILLMService"].called


@pytest.mark.integration
def test_stt_service_is_constructed(pipeline_mocks):
    from core.voice.pipeline import build_pipeline

    agent = VoiceAgent(name="hope", system_prompt="test", voice_id="v1")
    build_pipeline(agent, [])

    assert pipeline_mocks["OpenAISTTService"].called


@pytest.mark.integration
def test_transport_is_constructed(pipeline_mocks):
    from core.voice.pipeline import build_pipeline

    agent = VoiceAgent(name="hope", system_prompt="test", voice_id="v1")
    build_pipeline(agent, [])

    assert pipeline_mocks["LocalAudioTransport"].called


@pytest.mark.integration
def test_tts_does_not_receive_api_key(pipeline_mocks):
    """KokoroTTSService is local — no API key should be passed."""
    from core.voice.pipeline import build_pipeline

    agent = VoiceAgent(name="hope", system_prompt="test", voice_id="af_heart")
    build_pipeline(agent, [])

    call_kwargs = pipeline_mocks["KokoroTTSService"].call_args.kwargs
    assert "api_key" not in call_kwargs


@pytest.mark.integration
def test_pipeline_is_constructed_with_processors(pipeline_mocks):
    from core.voice.pipeline import build_pipeline

    agent = VoiceAgent(name="hope", system_prompt="test", voice_id="v1")
    build_pipeline(agent, [])

    mock_pipeline_cls = pipeline_mocks["Pipeline"]
    assert mock_pipeline_cls.called
    # Pipeline receives a list of processors as first positional arg
    processors = mock_pipeline_cls.call_args[0][0]
    assert isinstance(processors, list)
    assert len(processors) > 0


@pytest.mark.integration
def test_bundle_has_context_meter(pipeline_mocks, hope_voice_agent):
    from core.voice.pipeline import build_pipeline
    bundle = build_pipeline(hope_voice_agent, [])
    assert bundle.meter is not None
    assert bundle.meter.context_limit > 0


@pytest.mark.integration
def test_pipeline_includes_context_summarizer(pipeline_mocks, hope_voice_agent):
    from core.voice.pipeline import build_pipeline
    build_pipeline(hope_voice_agent, [])
    processors = pipeline_mocks["Pipeline"].call_args[0][0]
    assert pipeline_mocks["ContextSummarizer"].return_value in processors


@pytest.mark.integration
def test_pipeline_includes_team_broadcast_observer(pipeline_mocks, hope_voice_agent):
    from core.voice.pipeline import build_pipeline
    build_pipeline(hope_voice_agent, [])
    processors = pipeline_mocks["Pipeline"].call_args[0][0]
    assert pipeline_mocks["TeamBroadcastObserver"].return_value in processors


@pytest.mark.integration
def test_bundle_exposes_summarizer_for_shutdown_flush(pipeline_mocks, hope_voice_agent):
    """hope.py's shutdown finally block calls bundle.summarizer.flush() —
    the summarizer must be reachable off the bundle, not just wired into the
    internal pipeline processor list."""
    from core.voice.pipeline import build_pipeline
    bundle = build_pipeline(hope_voice_agent, [])
    assert bundle.summarizer is pipeline_mocks["ContextSummarizer"].return_value

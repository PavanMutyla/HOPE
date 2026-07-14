"""Unit tests for StatusPanel and StatusMonitor."""

import pytest
from core.status import StatusPanel


@pytest.mark.unit
def test_initial_state_is_listening():
    panel = StatusPanel()
    assert "Listening" in panel.state


@pytest.mark.unit
def test_set_state_updates():
    panel = StatusPanel()
    panel.set_state("custom-state")
    assert panel.state == "custom-state"


@pytest.mark.unit
def test_set_transcript_updates():
    panel = StatusPanel()
    panel.set_transcript("Hello HOPE")
    assert panel.last_transcript == "Hello HOPE"


@pytest.mark.unit
def test_handle_frame_user_started_speaking():
    from pipecat.frames.frames import UserStartedSpeakingFrame
    from core.status import StatusMonitor

    panel = StatusPanel()
    monitor = StatusMonitor(panel)
    monitor._handle_frame(UserStartedSpeakingFrame())
    assert "Listening" in panel.state


@pytest.mark.unit
def test_handle_frame_transcription():
    from pipecat.frames.frames import TranscriptionFrame
    from core.status import StatusMonitor

    panel = StatusPanel()
    monitor = StatusMonitor(panel)
    monitor._handle_frame(TranscriptionFrame(text="hi", user_id="u1", timestamp=""))
    assert panel.last_transcript == "hi"


@pytest.mark.unit
def test_handle_frame_llm_start():
    from pipecat.frames.frames import LLMFullResponseStartFrame
    from core.status import StatusMonitor

    panel = StatusPanel()
    monitor = StatusMonitor(panel)
    monitor._handle_frame(LLMFullResponseStartFrame())
    assert "Thinking" in panel.state


@pytest.mark.unit
def test_handle_frame_tts_started():
    from pipecat.frames.frames import TTSStartedFrame
    from core.status import StatusMonitor

    panel = StatusPanel()
    monitor = StatusMonitor(panel)
    monitor._handle_frame(TTSStartedFrame())
    assert "Speaking" in panel.state


@pytest.mark.unit
def test_handle_frame_tts_stopped():
    from pipecat.frames.frames import TTSStoppedFrame
    from core.status import StatusMonitor

    panel = StatusPanel()
    monitor = StatusMonitor(panel)
    monitor._handle_frame(TTSStoppedFrame())
    assert "Listening" in panel.state


@pytest.mark.unit
def test_unrecognised_frame_does_not_change_state():
    from pipecat.frames.frames import Frame
    from core.status import StatusMonitor

    panel = StatusPanel()
    monitor = StatusMonitor(panel)
    initial = panel.state
    monitor._handle_frame(Frame())
    assert panel.state == initial


@pytest.mark.unit
def test_set_usage_updates_usage_line():
    panel = StatusPanel()
    panel.set_usage(last_prompt=1200, last_completion=80, total=5400, context_pct=0.034, ttfb=0.41)
    assert "1200" in panel.usage_line
    assert "80" in panel.usage_line
    assert "5400" in panel.usage_line
    assert "3.4%" in panel.usage_line
    assert "0.41" in panel.usage_line


@pytest.mark.unit
def test_usage_line_empty_before_first_turn():
    panel = StatusPanel()
    assert panel.usage_line == ""


@pytest.mark.unit
def test_render_includes_usage_line():
    panel = StatusPanel()
    panel.set_usage(last_prompt=10, last_completion=5, total=15, context_pct=0.5, ttfb=0.2)
    rendered = panel._render()
    # Panel renderable contains the usage text
    text = rendered.renderable.plain
    assert "Tokens" in text


@pytest.mark.unit
def test_agent_name_empty_by_default():
    panel = StatusPanel()
    assert panel.agent_name == ""


@pytest.mark.unit
def test_set_agent_updates_agent_name():
    panel = StatusPanel()
    panel.set_agent("atlas")
    assert panel.agent_name == "atlas"


@pytest.mark.unit
def test_render_includes_agent_line_when_set():
    panel = StatusPanel()
    panel.set_agent("atlas")
    rendered = panel._render()
    text = rendered.renderable.plain
    assert "Agent:  atlas" in text
    # the agent line must be the first content line, above State
    assert text.index("Agent:") < text.index("State:")


@pytest.mark.unit
def test_render_omits_agent_line_when_empty():
    panel = StatusPanel()
    rendered = panel._render()
    text = rendered.renderable.plain
    assert "Agent:" not in text

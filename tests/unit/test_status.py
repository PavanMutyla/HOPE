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

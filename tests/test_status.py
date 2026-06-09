from pipecat.frames.frames import (
    UserStartedSpeakingFrame,
    TranscriptionFrame,
    LLMFullResponseStartFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TextFrame,
)
from core.status import StatusPanel, StatusMonitor


def test_initial_state_is_listening():
    panel = StatusPanel()
    assert panel.state == "🎙  Listening..."


def test_set_state_updates():
    panel = StatusPanel()
    panel.set_state("🧠  Thinking...")
    assert panel.state == "🧠  Thinking..."


def test_set_transcript_updates():
    panel = StatusPanel()
    panel.set_transcript("hello hope")
    assert panel.last_transcript == "hello hope"


def test_handle_frame_user_started_speaking():
    panel = StatusPanel()
    panel.set_state("🔊  Speaking...")
    monitor = StatusMonitor(panel)
    monitor._handle_frame(UserStartedSpeakingFrame())
    assert panel.state == "🎙  Listening..."


def test_handle_frame_transcription():
    panel = StatusPanel()
    monitor = StatusMonitor(panel)
    monitor._handle_frame(TranscriptionFrame(text="remind me about standup", user_id="user", timestamp="0"))
    assert panel.last_transcript == "remind me about standup"


def test_handle_frame_llm_start():
    panel = StatusPanel()
    monitor = StatusMonitor(panel)
    monitor._handle_frame(LLMFullResponseStartFrame())
    assert panel.state == "🧠  Thinking..."


def test_handle_frame_tts_started():
    panel = StatusPanel()
    monitor = StatusMonitor(panel)
    monitor._handle_frame(TTSStartedFrame())
    assert panel.state == "🔊  Speaking..."


def test_handle_frame_tts_stopped():
    panel = StatusPanel()
    monitor = StatusMonitor(panel)
    panel.set_state("🔊  Speaking...")
    monitor._handle_frame(TTSStoppedFrame())
    assert panel.state == "🎙  Listening..."


def test_unrecognised_frame_does_not_change_state():
    panel = StatusPanel()
    monitor = StatusMonitor(panel)
    panel.set_state("🧠  Thinking...")
    monitor._handle_frame(TextFrame(text="some text"))
    assert panel.state == "🧠  Thinking..."

from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import (
    UserStartedSpeakingFrame,
    TranscriptionFrame,
    LLMFullResponseStartFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)


class StatusPanel:
    def __init__(self):
        self.state = "🎙  Listening..."
        self.last_transcript = ""
        self._live = Live(refresh_per_second=4)
        self._started = False

    def start(self):
        self._live.start()
        self._started = True
        self._refresh()

    def stop(self):
        if self._started:
            self._live.stop()
            self._started = False

    def set_state(self, state: str):
        self.state = state
        self._refresh()

    def set_transcript(self, text: str):
        self.last_transcript = text
        self._refresh()

    def _refresh(self):
        if self._started:
            self._live.update(self._render())

    def _render(self) -> Panel:
        content = Text()
        content.append(f"  State:  {self.state}\n")
        if self.last_transcript:
            content.append(f"  You:    \"{self.last_transcript}\"")
        return Panel(content, title="HOPE", border_style="cyan")


class StatusMonitor(FrameProcessor):
    def __init__(self, panel: StatusPanel):
        super().__init__()
        self._panel = panel

    def _handle_frame(self, frame) -> None:
        if isinstance(frame, UserStartedSpeakingFrame):
            self._panel.set_state("🎙  Listening...")
        elif isinstance(frame, TranscriptionFrame):
            self._panel.set_transcript(frame.text)
        elif isinstance(frame, LLMFullResponseStartFrame):
            self._panel.set_state("🧠  Thinking...")
        elif isinstance(frame, TTSStartedFrame):
            self._panel.set_state("🔊  Speaking...")
        elif isinstance(frame, TTSStoppedFrame):
            self._panel.set_state("🎙  Listening...")

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        self._handle_frame(frame)
        await self.push_frame(frame, direction)

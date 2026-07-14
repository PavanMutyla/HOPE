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
        self.usage_line = ""
        self.agent_name = ""
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

    def set_agent(self, name: str):
        self.agent_name = name
        self._refresh()

    def set_transcript(self, text: str):
        self.last_transcript = text
        self._refresh()

    def set_usage(self, last_prompt: int, last_completion: int, total: int,
                  context_pct: float, ttfb: float):
        self.usage_line = (
            f"{last_prompt} in / {last_completion} out"
            f"  •  total {total}"
            f"  •  ctx {context_pct:.1%}"
            f"  •  ttfb {ttfb:.2f}s"
        )
        self._refresh()

    def _refresh(self):
        if self._started:
            self._live.update(self._render())

    def _render(self) -> Panel:
        content = Text()
        if self.agent_name:
            content.append(f"  Agent:  {self.agent_name}\n")
        content.append(f"  State:  {self.state}\n")
        if self.last_transcript:
            content.append(f"  You:    \"{self.last_transcript}\"")
        if self.usage_line:
            content.append(f"\n  Tokens: {self.usage_line}")
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

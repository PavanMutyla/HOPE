"""LiveFeedObserver — the pipeline's only outbound channel to the dashboard.

The dashboard runs as a separate OS process and cannot see `StatusPanel`,
`LLMContext` or `agent_state`, so anything it should display has to be written
somewhere both processes can reach. This is the sidecar that does that,
mirroring `StatusMonitor` (terminal) and `TeamBroadcastObserver` (team voices):
a pass-through `FrameProcessor` that observes frames and never modifies them.

Assistant text is the reason this can't just tail `hope.log`. `StatusPanel`
already logs user transcripts, state changes and token usage, but HOPE's own
replies are never logged anywhere — they only exist as a stream of
`LLMTextFrame`s. So they're accumulated here between
`LLMFullResponseStartFrame` and `LLMFullResponseEndFrame` and written as one
finished turn.

Every write is best-effort: a failure here must never disturb the audio
pipeline, which is the whole product. A dashboard that goes stale is a much
smaller problem than a pipeline that stalls on a locked database.
"""

from loguru import logger

from pipecat.frames.frames import (
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TranscriptionFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    UserStartedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from core.voice.agent_state import agent_state
from memory.live.store import LiveFeed


class LiveUserTap(FrameProcessor):
    """Writes Pavan's side of the conversation. Place it between STT and
    `context_aggregator.user()`: the user aggregator consumes every final
    `TranscriptionFrame` and never pushes it on, so nothing downstream of it,
    LiveFeedObserver included, ever sees what Pavan said.

    Split from LiveFeedObserver rather than placing one class twice, because
    each turn has to be appended exactly once: this writes only user turns,
    that writes only assistant turns.
    """

    def __init__(self, feed: LiveFeed, session_id: str):
        super().__init__()
        self._feed = feed
        self._session_id = session_id

    def _handle_frame(self, frame) -> None:
        try:
            if isinstance(frame, UserStartedSpeakingFrame):
                self._feed.set_state("listening")
            elif isinstance(frame, TranscriptionFrame):
                text = (frame.text or "").strip()
                if text:
                    self._feed.append_turn(self._session_id, "user", "", text)
        except Exception:
            logger.exception("Live feed user turn failed — dashboard may be stale")

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        self._handle_frame(frame)
        await self.push_frame(frame, direction)


class LiveFeedObserver(FrameProcessor):
    """Writes HOPE's side: place it downstream of the LLM, where the reply
    streams past as `LLMTextFrame`s. User turns are LiveUserTap's job."""

    def __init__(self, feed: LiveFeed, session_id: str, meter=None):
        super().__init__()
        self._feed = feed
        self._session_id = session_id
        # Read-only borrow of the ContextMeter so the dashboard can show the
        # same context_pct the terminal panel shows. Reading it here beats
        # threading a second writer through ContextSummarizer, which owns the
        # meter's update path and shouldn't grow a dashboard dependency.
        self._meter = meter
        self._reply_parts: list[str] = []

    def _safe(self, what: str, fn, *args) -> None:
        try:
            fn(*args)
        except Exception:
            logger.exception(f"Live feed {what} failed — dashboard may be stale")

    def _handle_frame(self, frame) -> None:
        if isinstance(frame, LLMFullResponseStartFrame):
            self._reply_parts = []
            self._safe("state", self._feed.set_state, "thinking")

        elif isinstance(frame, LLMTextFrame):
            self._reply_parts.append(frame.text or "")

        elif isinstance(frame, LLMFullResponseEndFrame):
            reply = "".join(self._reply_parts).strip()
            self._reply_parts = []
            # A tool-call turn produces no text at all — nothing to show, and
            # writing an empty bubble would look like HOPE said nothing.
            if reply:
                self._safe(
                    "assistant turn", self._feed.append_turn,
                    self._session_id, "assistant", agent_state.active, reply,
                )
                self._safe("agent", self._feed.set_agent, agent_state.active)
                if self._meter is not None:
                    self._safe(
                        "context pct", self._feed.set_context_pct,
                        self._meter.context_pct,
                    )

        elif isinstance(frame, TTSStartedFrame):
            self._safe("state", self._feed.set_state, "speaking")

        elif isinstance(frame, TTSStoppedFrame):
            self._safe("state", self._feed.set_state, "listening")

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        self._handle_frame(frame)
        await self.push_frame(frame, direction)

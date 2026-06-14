import time

from langfuse import Langfuse
from loguru import logger

from pipecat.frames.frames import (
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from settings import settings


class LangfuseTracer:
    """Shared state for one voice turn — passed into two LangfuseObserver positions."""

    def __init__(self):
        self._lf = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_base_url,
        )
        self._turn_span = None
        self._stt_span = None
        self._llm_gen = None
        self._llm_chunks: list[str] = []
        self._transcript = ""
        self._t_stopped: float | None = None
        self._t_stt: float | None = None
        self._t_llm: float | None = None
        self._t_tts: float | None = None

    def on_frame(self, frame) -> None:
        try:
            if isinstance(frame, UserStartedSpeakingFrame):
                self._start_turn()
            elif isinstance(frame, UserStoppedSpeakingFrame):
                self._t_stopped = time.perf_counter()
            elif isinstance(frame, TranscriptionFrame):
                self._end_stt(frame.text)
            elif isinstance(frame, LLMFullResponseStartFrame):
                self._start_llm()
            elif isinstance(frame, LLMTextFrame):
                self._llm_chunks.append(frame.text)
            elif isinstance(frame, LLMFullResponseEndFrame):
                self._end_llm()
            elif isinstance(frame, TTSStartedFrame):
                self._start_tts()
            elif isinstance(frame, TTSStoppedFrame):
                self._end_turn()
        except Exception:
            logger.exception("Langfuse tracing error (non-fatal)")

    # ── turn lifecycle ──────────────────────────────────────────────────────

    def _start_turn(self):
        self._llm_chunks = []
        self._transcript = ""
        self._t_stopped = self._t_stt = self._t_llm = self._t_tts = None
        self._turn_span = self._lf.start_observation(
            name="hope-turn",
            as_type="span",
            metadata={"user": settings.user_name},
        )
        self._stt_span = self._turn_span.start_observation(
            name="stt",
            as_type="span",
        )

    def _end_stt(self, text: str):
        self._t_stt = time.perf_counter()
        self._transcript = text
        if self._stt_span:
            self._stt_span.update(
                output={"transcript": text},
                metadata={"model": settings.stt_model},
            )
            self._stt_span.end()
            self._stt_span = None

    def _start_llm(self):
        self._t_llm = time.perf_counter()
        if self._turn_span:
            self._llm_gen = self._turn_span.start_observation(
                name="llm",
                as_type="generation",
                model=settings.llm_model,
                input=self._transcript,
            )

    def _end_llm(self):
        if self._llm_gen:
            output = "".join(self._llm_chunks)
            self._llm_gen.update(output=output)
            self._llm_gen.end()
            self._llm_gen = None

    def _start_tts(self):
        self._t_tts = time.perf_counter()
        if self._turn_span:
            self._tts_span = self._turn_span.start_observation(
                name="tts",
                as_type="span",
            )

    def _end_turn(self):
        if hasattr(self, "_tts_span") and self._tts_span:
            self._tts_span.end()
            self._tts_span = None
        if self._turn_span:
            self._turn_span.set_trace_io(
                input=self._transcript,
                output="".join(self._llm_chunks),
            )
            self._turn_span.end()
            self._turn_span = None
        self._log_latency()
        self._lf.flush()

    def _log_latency(self):
        if not self._t_stopped:
            return
        now = time.perf_counter()
        stt_ms  = (self._t_stt - self._t_stopped) * 1000  if self._t_stt  else 0
        llm_ms  = (self._t_llm - self._t_stt)     * 1000  if self._t_llm and self._t_stt else 0
        tts_ms  = (self._t_tts - self._t_llm)     * 1000  if self._t_tts and self._t_llm else 0
        total_ms = (now - self._t_stopped)         * 1000
        logger.info(
            f"latency | stt {stt_ms:.0f}ms  llm {llm_ms:.0f}ms  tts {tts_ms:.0f}ms  "
            f"| total {total_ms:.0f}ms"
        )

    def shutdown(self):
        self._lf.shutdown()


class LangfuseObserver(FrameProcessor):
    """Passthrough processor that feeds frames into LangfuseTracer."""

    def __init__(self, tracer: LangfuseTracer):
        super().__init__()
        self._tracer = tracer

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        self._tracer.on_frame(frame)
        await self.push_frame(frame, direction)

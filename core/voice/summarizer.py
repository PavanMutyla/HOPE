"""Pure functions for splitting and rebuilding LLM context around summarization,
plus the ContextSummarizer frame processor that wires them into the pipeline.
"""

import asyncio

from loguru import logger
from pipecat.frames.frames import MetricsFrame
from pipecat.metrics.metrics import LLMUsageMetricsData, TTFBMetricsData
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

from core.voice.agent_state import agent_state
from core.voice.context_meter import ContextMeter
from core.status import StatusPanel
from memory.episodic_memory.store import EpisodicMemory
from settings import settings

SUMMARY_MAX_CONTEXT_PCT = 0.2  # summary output caps at 20% of the model's context window

SUMMARY_SYSTEM_PROMPT = (
    "You compress conversation history for a voice assistant. Write a concise "
    "summary of the conversation below. Preserve: decisions made, facts stated, "
    "user preferences, unresolved questions, and task state. Omit filler and "
    "pleasantries. Write in third person ('Pavan asked...', 'HOPE confirmed...')."
)


def split_for_summary(
    messages: list[dict], keep_recent: int
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split messages into (system_msgs, to_summarize, recent).

    The boundary slides backwards past 'tool' messages so a tool result is
    never separated from the assistant tool_calls message that owns it.
    """
    start = 1 if messages and messages[0].get("role") == "system" else 0
    boundary = min(max(len(messages) - keep_recent, start), len(messages))
    system_msgs = messages[:start]
    while (
        boundary > start
        and boundary < len(messages)
        and messages[boundary].get("role") == "tool"
    ):
        boundary -= 1  # step back to the tool result's siblings...
    # ...and one more if we landed just after an assistant tool_calls message
    # (only matters when there's a "recent" portion to protect — if the
    # boundary is already at the end, the pair sits together in head and
    # there's nothing to slide back for)
    if (
        boundary > start
        and boundary < len(messages)
        and messages[boundary - 1].get("role") == "assistant"
        and messages[boundary - 1].get("tool_calls")
    ):
        boundary -= 1
    return system_msgs, messages[start:boundary], messages[boundary:]


def _as_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, list):  # multimodal parts — keep text parts only
        content = " ".join(
            p.get("text", "") for p in content if isinstance(p, dict)
        )
    if content is None:
        content = f"[tool calls: {[c.get('id') for c in message.get('tool_calls', [])]}]"
    return f"{message.get('role', '?')}: {content}"


def build_summary_request(to_summarize: list[dict]) -> list[dict]:
    transcript = "\n".join(_as_text(m) for m in to_summarize)
    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": transcript},
    ]


def rebuild_context(
    system_msgs: list[dict], summary: str, recent: list[dict]
) -> list[dict]:
    summary_message = {
        "role": "developer",
        "content": f"Summary of the earlier conversation (auto-generated): {summary}",
    }
    return [*system_msgs, summary_message, *recent]


class ContextSummarizer(FrameProcessor):
    """Watches LLM usage metrics; updates the panel; when the context crosses
    the threshold, summarizes older turns in a background task and rewrites
    the live context. Never blocks the frame pipeline."""

    def __init__(
        self,
        context,
        meter: ContextMeter,
        panel: StatusPanel,
        client,
        episodic_memory: EpisodicMemory,
        session_id: str,
    ):
        super().__init__()
        self._context = context
        self._meter = meter
        self._panel = panel
        self._client = client
        self._episodic_memory = episodic_memory
        self._session_id = session_id
        self._keep_recent = settings.context_keep_recent
        self._summary_task: asyncio.Task | None = None

    def _handle_metrics(self, frame: MetricsFrame) -> None:
        for item in frame.data:
            if isinstance(item, TTFBMetricsData):
                self._meter.record_ttfb(item.value)
            elif isinstance(item, LLMUsageMetricsData):
                self._meter.record_usage(item.value)
                self._panel.set_usage(
                    last_prompt=self._meter.last_prompt_tokens,
                    last_completion=self._meter.last_completion_tokens,
                    total=self._meter.total_prompt_tokens + self._meter.total_completion_tokens,
                    context_pct=self._meter.context_pct,
                    ttfb=self._meter.last_ttfb,
                )
                if self._meter.should_summarize() and (
                    self._summary_task is None or self._summary_task.done()
                ):
                    self._summary_task = asyncio.create_task(self._summarize())

    async def _summarize(self) -> None:
        try:
            snapshot = list(self._context.messages)
            system_msgs, head, recent = split_for_summary(snapshot, self._keep_recent)
            if not head:
                return
            response = await self._client.chat.completions.create(
                model=settings.summarizer_model,
                messages=build_summary_request(head),
                max_tokens=max(1, int(self._meter.context_limit * SUMMARY_MAX_CONTEXT_PCT)),
            )
            summary = response.choices[0].message.content or ""
            # an agent switch may have replaced messages[0] while we awaited
            # the summary call above — use the live system message, not the
            # stale snapshot, so the rebuild doesn't revert the switch.
            live_messages = self._context.messages
            if live_messages and live_messages[0].get("role") == "system":
                system_msgs = [live_messages[0]]
            rebuilt = rebuild_context(system_msgs, summary, recent)
            # keep any turns that arrived while the summary call was in flight
            rebuilt.extend(live_messages[len(snapshot):])
            self._context.set_messages(rebuilt)
            logger.info(
                f"Context summarized: {len(snapshot)} → {len(rebuilt)} messages"
            )
        except Exception:
            logger.exception("Context summarization failed — continuing unsummarized")
            return

        await self._write_episodic(head, summary)

    async def _write_episodic(self, head: list[dict], summary: str) -> None:
        """Best-effort persistence of the fold just performed above. Runs in a
        thread since sqlite3/chromadb are blocking calls — failure here must
        never undo or be confused with the summarization that already
        succeeded, hence the separate try/except from _summarize()'s own."""
        try:
            await asyncio.to_thread(
                self._episodic_memory.write,
                agent=agent_state.active,
                session_id=self._session_id,
                reason="threshold",
                span_turns=len(head),
                summary=summary,
                messages=head,
            )
        except Exception:
            logger.exception("Episodic memory write failed — continuing without persistence")

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, MetricsFrame):
            self._handle_metrics(frame)
        await self.push_frame(frame, direction)

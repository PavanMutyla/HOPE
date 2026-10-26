"""Pure functions for splitting and rebuilding LLM context around summarization,
plus the ContextSummarizer frame processor that wires them into the pipeline.
"""

import asyncio

from loguru import logger
from pipecat.frames.frames import MetricsFrame
from pipecat.metrics.metrics import LLMUsageMetricsData, TTFBMetricsData
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

from core.voice.context_meter import ContextMeter
from core.status import StatusPanel
from memory.episodic_memory.store import EpisodicMemory
from memory.semantic_memory.store import SemanticMemory
from settings import settings

SUMMARY_MAX_CONTEXT_PCT = 0.2  # summary output caps at 20% of the model's context window

UNSUMMARIZED_MARKER = "[NOT SUMMARIZED YET — raw session tail, pending upgrade at next startup]"

SUMMARY_SYSTEM_PROMPT = (
    "You compress conversation history for a voice assistant. Write a concise "
    "summary of the conversation below. Preserve: decisions made, facts stated, "
    "user preferences, unresolved questions, and task state. Omit filler and "
    "pleasantries. Write in third person ('Pavan asked...', 'HOPE confirmed...')."
)

# The one kind of `developer` message that is this session's own content: a
# fold of its earlier turns. Every other developer message is scaffolding the
# pipeline adds itself — last session's warm-start recap, the greeting prompt.
FOLD_SUMMARY_PREFIX = "Summary of the earlier conversation (auto-generated): "


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


def summarizable(messages: list[dict]) -> list[dict]:
    """What the summarizer should read: the conversation, minus scaffolding.

    The warm-start recap is the one that matters. Left in, the summarizer
    reads last session's recap as something that happened in this session
    and writes it into this session's summary, which becomes the next
    session's recap, and so on: one August session's "team mode, tried to
    contact Suresh" ended up opening every summary for months after. A fold
    summary is kept, since it is this session's own earlier turns."""
    return [
        m for m in messages
        if m.get("role") != "developer"
        or str(m.get("content") or "").startswith(FOLD_SUMMARY_PREFIX)
    ]


def has_user_turn(messages: list[dict]) -> bool:
    return any(m.get("role") == "user" for m in messages)


def build_summary_request(to_summarize: list[dict]) -> list[dict]:
    transcript = "\n".join(_as_text(m) for m in summarizable(to_summarize))
    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": transcript},
    ]


def rebuild_context(
    system_msgs: list[dict], summary: str, recent: list[dict]
) -> list[dict]:
    summary_message = {
        "role": "developer",
        "content": f"{FOLD_SUMMARY_PREFIX}{summary}",
    }
    return [*system_msgs, summary_message, *recent]


class ContextSummarizer(FrameProcessor):
    """Watches LLM usage metrics; updates the panel; when the context crosses
    the threshold, summarizes older turns in a background task and rewrites
    the live context. Never blocks the frame pipeline.

    Everything it writes is tagged `owner` (HOPE), not whichever agent holds
    the pipeline at that moment. Atlas and the researchers are guests on
    HOPE's conversation; tagging by the active agent filed a whole session
    under "atlas" because Pavan happened to be talking to Atlas when he quit,
    which hid it from HOPE's recall and from the next warm start."""

    def __init__(
        self,
        context,
        meter: ContextMeter,
        panel: StatusPanel,
        client,
        episodic_memory: EpisodicMemory,
        session_id: str,
        semantic_memory: SemanticMemory,
        owner: str = "hope",
    ):
        super().__init__()
        self._owner = owner
        self._context = context
        self._meter = meter
        self._panel = panel
        self._client = client
        self._episodic_memory = episodic_memory
        self._session_id = session_id
        self._semantic_memory = semantic_memory
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
        await self._write_semantic(self._owner, summary)

    async def flush(self) -> None:
        """Fast, LLM-free archive of whatever's still live in context at
        shutdown — without this, a session that never crossed the fold
        threshold would be lost entirely when the process exits. Tagged
        'session_end_raw'; upgrade_pending_episodes() below replaces it with
        a real LLM summary at the next startup.

        No semantic write here on purpose — this is deliberately LLM-free to
        avoid blocking shutdown on an API call, and raw unsummarized text is
        poor input for fact extraction anyway. Semantic write happens once
        in upgrade_pending_episodes() instead, against the real summary."""
        snapshot = list(self._context.messages)
        # keep_recent=0 -> split_for_summary puts the entire non-system
        # conversation into `to_archive`; nothing is held back as "recent."
        _, to_archive, _ = split_for_summary(snapshot, keep_recent=0)
        # A run where Pavan never spoke is HOPE's greeting and nothing else.
        # Saving it would make it "the latest session", and the next warm
        # start would recap an empty run instead of the last real one.
        if not has_user_turn(to_archive):
            return
        try:
            raw_text = "\n".join(_as_text(m) for m in to_archive)
            await asyncio.to_thread(
                self._episodic_memory.write,
                agent=self._owner,
                session_id=self._session_id,
                reason="session_end_raw",
                span_turns=len(to_archive),
                summary=f"{UNSUMMARIZED_MARKER}\n{raw_text}",
                messages=to_archive,
            )
        except Exception:
            logger.exception("Session-close flush failed — conversation not persisted")

    async def _write_episodic(self, head: list[dict], summary: str) -> None:
        """Best-effort persistence of the fold just performed above. Runs in a
        thread since sqlite3/chromadb are blocking calls — failure here must
        never undo or be confused with the summarization that already
        succeeded, hence the separate try/except from _summarize()'s own."""
        try:
            await asyncio.to_thread(
                self._episodic_memory.write,
                agent=self._owner,
                session_id=self._session_id,
                reason="threshold",
                span_turns=len(head),
                summary=summary,
                messages=head,
            )
        except Exception:
            logger.exception("Episodic memory write failed — continuing without persistence")

    async def _write_semantic(self, agent: str, text: str) -> None:
        """Best-effort fact extraction from the summary just written to
        episodic memory. Separate try/except from _write_episodic — a
        semantic-layer failure must never be confused with, or undo, the
        episodic write that already succeeded."""
        try:
            await asyncio.to_thread(self._semantic_memory.add, agent=agent, text=text)
        except Exception:
            logger.exception("Semantic memory write failed — continuing without persistence")

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, MetricsFrame):
            self._handle_metrics(frame)
        await self.push_frame(frame, direction)


async def upgrade_pending_episodes(
    episodic_memory: EpisodicMemory, client, semantic_memory: SemanticMemory
) -> None:
    """Startup pass: replace every episode ContextSummarizer.flush() archived
    raw at the end of a previous session (reason='session_end_raw') with a
    real LLM summary, same summarization used for a normal threshold fold.
    Also the semantic-memory write point for session-end episodes — deferred
    here rather than into flush() itself, since flush() is deliberately
    LLM-free and this is the first point a real summary exists for
    'session_end_raw' episodes.

    Self-healing: an episode that fails to upgrade (e.g. API unreachable)
    just stays 'session_end_raw' and gets retried on the next startup — never
    raises, since a memory-quality pass must never block HOPE from starting."""
    pending = await asyncio.to_thread(episodic_memory.list_by_reason, "session_end_raw")
    for episode in pending:
        try:
            raw_messages = [{"role": m.role, "content": m.content_text} for m in episode.messages]
            response = await client.chat.completions.create(
                model=settings.summarizer_model,
                messages=build_summary_request(raw_messages),
            )
            summary = response.choices[0].message.content or ""
            await asyncio.to_thread(episodic_memory.upgrade, episode.id, episode.agent, summary)
            logger.info(f"Upgraded episode {episode.id} to a real summary")
        except Exception:
            logger.exception(f"Failed to upgrade episode {episode.id} — will retry next startup")
            continue

        try:
            await asyncio.to_thread(semantic_memory.add, agent=episode.agent, text=summary)
        except Exception:
            logger.exception(f"Semantic memory write failed for episode {episode.id}")


async def inject_warm_start(episodic_memory: EpisodicMemory, context, agent: str = "hope") -> None:
    """Startup: if the last session for `agent` was cleanly closed and
    summarized, inject that summary into the new session's opening context so
    the conversation can pick up where it left off. Best-effort — a lookup
    failure or a first-ever run (no prior session_end episode) must never
    block startup, just skip the injection silently."""
    try:
        last_session = await asyncio.to_thread(episodic_memory.get_latest_by_reason, "session_end", agent)
    except Exception:
        logger.exception("Warm-start lookup failed — starting without prior-session context")
        return
    if last_session is None:
        return
    context.add_message({
        "role": "developer",
        "content": (
            "Summary of your most recent session with Pavan (for context — "
            f"don't repeat it verbatim): {last_session.summary}"
        ),
    })

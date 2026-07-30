"""EpisodicMemory facade — the single entry point callers use to persist and
retrieve episodic entries. Wires episodic.py (SQLite, source of truth for
raw/multimodal content) and vector_store.py (Chroma, semantic index over
summaries) together. See docs/HOPE_Episodic_Storage_Design.md.

sqlite3 and chromadb calls here are synchronous/blocking. The intended caller
is ContextSummarizer's fire-and-forget fold task (core/voice/summarizer.py),
which should offload `write()` via `asyncio.to_thread` so a slow embed/DB
write never blocks the pipeline — that wiring is done at the call site, not
inside this class.
"""

from pathlib import Path
from typing import Any

from memory.episodic_memory import episodic, plans
from memory.episodic_memory.schema import Episode, Plan
from memory.episodic_memory.vector_store import EpisodicVectorStore
from settings import settings


class EpisodicMemory:
    def __init__(
        self,
        db_path: str | Path | None = None,
        media_dir: str | Path | None = None,
        persist_dir: str | Path | None = None,
        embedding_function: Any = None,
    ):
        self._media_dir = Path(media_dir or settings.episodic_media_dir)
        self._conn = episodic.connect(db_path or settings.episodic_db_path)
        self._vectors = EpisodicVectorStore(
            persist_dir or settings.chroma_persist_dir,
            embedding_function=embedding_function,
        )

    def write(
        self,
        agent: str,
        session_id: str,
        reason: str,
        span_turns: int,
        summary: str,
        messages: list[dict],
    ) -> str:
        episode_id = episodic.create_episode(
            self._conn,
            self._media_dir,
            agent,
            session_id,
            reason,
            span_turns,
            summary,
            messages,
        )
        self._vectors.upsert(episode_id, summary, {"agent": agent, "reason": reason})
        return episode_id

    def query(self, text: str, k: int = 5, agent: str | None = None) -> list[Episode]:
        episode_ids = self._vectors.query(text, k, agent=agent)
        episodes = (episodic.get_episode(self._conn, episode_id) for episode_id in episode_ids)
        return [episode for episode in episodes if episode is not None]

    def list_by_reason(self, reason: str) -> list[Episode]:
        episode_ids = episodic.list_episodes_by_reason(self._conn, reason)
        episodes = (episodic.get_episode(self._conn, episode_id) for episode_id in episode_ids)
        return [episode for episode in episodes if episode is not None]

    def get_latest_by_reason(self, reason: str, agent: str | None = None) -> Episode | None:
        episode_id = episodic.get_latest_episode_by_reason(self._conn, reason, agent)
        return episodic.get_episode(self._conn, episode_id) if episode_id else None

    def upgrade(self, episode_id: str, agent: str, summary: str, reason: str = "session_end") -> None:
        """Replace a raw flush()-archived episode's summary with a real one,
        in place. Idempotent — re-upserting the same episode_id updates the
        existing vector rather than duplicating it."""
        episodic.update_episode_summary(self._conn, episode_id, summary, reason)
        self._vectors.upsert(episode_id, summary, {"agent": agent, "reason": reason})

    def close(self) -> None:
        self._conn.close()

    # ── Plan tracking ──────────────────────────────────────────────────
    # A plan is written down when formed, before anything happens — unlike
    # everything above, which only ever records what already occurred.

    def create_plan(self, agent: str, description: str) -> str:
        return plans.create_plan(self._conn, agent, description)

    def resolve_plan(self, plan_id: str, resulting_episode_id: str) -> None:
        plans.resolve_plan(self._conn, plan_id, resulting_episode_id)

    def abandon_plan(self, plan_id: str) -> None:
        plans.abandon_plan(self._conn, plan_id)

    def supersede_plan(self, plan_id: str, superseded_by: str) -> None:
        plans.supersede_plan(self._conn, plan_id, superseded_by)

    def get_plan(self, plan_id: str) -> Plan | None:
        return plans.get_plan(self._conn, plan_id)

    def list_plans(self, agent: str | None = None, status: str | None = None) -> list[Plan]:
        return plans.list_plans(self._conn, agent=agent, status=status)

"""SemanticMemory facade — the single entry point callers use to persist and
retrieve durable, time-independent facts. Wraps Mem0, which owns extraction,
dedup, and contradiction resolution internally; this class only adapts Mem0's
generic user_id/agent_id concepts to HOPE's scoping convention (user-scoped
by default, per-agent as an explicit escape hatch) and hides Mem0's filter/
kwarg shape from callers. See docs/HOPE_Semantic_Memory_Design.md.

mem0's add()/search() calls are synchronous/blocking (LLM + vector store
round trips). The intended callers (ContextSummarizer, Atlas) offload via
asyncio.to_thread at the call site, same pattern EpisodicMemory already uses
— that wiring lives there, not inside this class.
"""

from pathlib import Path
from typing import Any

from mem0 import Memory

from memory.semantic_memory.config import build_mem0_config
from settings import settings


class SemanticMemory:
    def __init__(
        self,
        persist_dir: str | Path | None = None,
        history_db_path: str | Path | None = None,
        client: Any = None,
    ):
        self._user_id = settings.user_name
        self._mem0 = client or Memory.from_config(
            build_mem0_config(persist_dir, history_db_path)
        )

    def add(self, agent: str, text: str) -> None:
        self._mem0.add(text, user_id=self._user_id, agent_id=agent)

    def query(self, text: str, k: int = 5, agent: str | None = None) -> list[dict]:
        filters = {"user_id": self._user_id}
        if agent is not None:
            filters["agent_id"] = agent
        response = self._mem0.search(text, filters=filters, limit=k)
        return response.get("results", [])

    def get_all(self, agent: str | None = None) -> list[dict]:
        """Every fact in scope, unranked — for audit export
        (scripts/export_semantic_facts.py), not for retrieval (use query())."""
        filters = {"user_id": self._user_id}
        if agent is not None:
            filters["agent_id"] = agent
        response = self._mem0.get_all(filters=filters)
        return response.get("results", [])

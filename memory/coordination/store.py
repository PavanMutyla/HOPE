"""Blackboard facade — the only thing tool handlers touch for the
coordination pool. Wires coordination.py (SQLite, source of truth for live
task/signal state) together with the existing episodic memory
`task_complete` write path, so a task resolving here still lands in the
durable historical record without any agent having to remember to write it
twice. See docs/HOPE_Coordination_Pool_Design.md.
"""

import threading
from pathlib import Path

from memory.coordination import coordination
from memory.coordination.schema import ResearchRun, ResearchSource, Signal, SubAgentRecord, Task
from memory.episodic_memory.store import EpisodicMemory
from settings import settings

_RESOLVED_STATUSES = {"completed", "failed"}


class Blackboard:
    def __init__(
        self,
        episodic_memory: EpisodicMemory,
        db_path: str | Path | None = None,
    ):
        self._conn = coordination.connect(db_path or settings.blackboard_db_path)
        self._episodic_memory = episodic_memory
        # One connection, many threads: tool handlers and every concurrently
        # running researcher reach this via asyncio.to_thread. sqlite3 alone
        # doesn't stop two threads' statements interleaving inside one
        # `with conn:` transaction, so every call takes this lock.
        self._lock = threading.Lock()

    def post_task(self, description: str, created_by: str, payload: str | None = None) -> str:
        with self._lock:
            return coordination.post_task(self._conn, description, created_by, payload)

    def claim_task(self, task_id: str, agent: str) -> bool:
        with self._lock:
            return coordination.claim_task(self._conn, task_id, agent)

    def update_task_status(self, task_id: str, status: str, detail: str | None = None) -> bool:
        """On status in ('completed', 'failed'), also writes a
        reason='task_complete' episode — the same durable-record path
        Atlas._write_episodic already uses for delegated filesystem tasks —
        so blackboard-coordinated work is recorded exactly once, not
        duplicated and not silently dropped when the row is later cleaned up
        (§8 of the design doc)."""
        with self._lock:
            task = coordination.get_task(self._conn, task_id)
            updated = coordination.update_task_status(self._conn, task_id, status, detail)

        if updated and status in _RESOLVED_STATUSES and task is not None:
            agent = task.owner_agent or task.created_by
            summary = f"Task: {task.description}\nStatus: {status}"
            if detail:
                summary += f"\nDetail: {detail}"
            self._episodic_memory.write(
                agent=agent,
                session_id=task_id,
                reason="task_complete",
                span_turns=1,
                summary=summary,
                messages=[],
            )

        return updated

    def get_active_tasks(self, agent_name: str | None = None) -> list[Task]:
        with self._lock:
            return coordination.get_active_tasks(self._conn, agent_name)

    def send_signal(self, from_agent: str, to_agent: str, payload: str) -> str:
        with self._lock:
            return coordination.send_signal(self._conn, from_agent, to_agent, payload)

    def get_signals_for(self, agent_name: str) -> list[Signal]:
        with self._lock:
            return coordination.get_signals_for(self._conn, agent_name)

    # ── Sub-agents ──

    def register_agent(
        self,
        spoken_name: str,
        template: str,
        voice_id: str,
        objective: str,
        run_id: str | None = None,
    ) -> str:
        with self._lock:
            return coordination.register_agent(
            self._conn, spoken_name, template, voice_id, objective, run_id
        )

    def set_agent_status(self, agent_id: str, status: str) -> bool:
        with self._lock:
            return coordination.set_agent_status(self._conn, agent_id, status)

    def retire_live_agents(self) -> int:
        with self._lock:
            return coordination.retire_live_agents(self._conn)

    def get_agent(self, agent_id: str) -> SubAgentRecord | None:
        with self._lock:
            return coordination.get_agent(self._conn, agent_id)

    def list_agents(self, include_retired: bool = False) -> list[SubAgentRecord]:
        with self._lock:
            return coordination.list_agents(self._conn, include_retired)

    # ── Research runs ──

    def create_run(self, question: str) -> str:
        with self._lock:
            return coordination.create_run(self._conn, question)

    def update_run(
        self,
        run_id: str,
        status: str,
        report_path: str | None = None,
        summary: str | None = None,
    ) -> bool:
        with self._lock:
            return coordination.update_run(self._conn, run_id, status, report_path, summary)

    def get_run(self, run_id: str) -> ResearchRun | None:
        with self._lock:
            return coordination.get_run(self._conn, run_id)

    def list_runs(self, limit: int = 5) -> list[ResearchRun]:
        with self._lock:
            return coordination.list_runs(self._conn, limit)

    def add_source(
        self, run_id: str, agent_id: str, url: str, title: str, content_hash: str
    ) -> bool:
        with self._lock:
            return coordination.add_source(self._conn, run_id, agent_id, url, title, content_hash)

    def list_sources(self, run_id: str) -> list[ResearchSource]:
        with self._lock:
            return coordination.list_sources(self._conn, run_id)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

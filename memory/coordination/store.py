"""Blackboard facade — the only thing tool handlers touch for the
coordination pool. Wires coordination.py (SQLite, source of truth for live
task/signal state) together with the existing episodic memory
`task_complete` write path, so a task resolving here still lands in the
durable historical record without any agent having to remember to write it
twice. See docs/HOPE_Coordination_Pool_Design.md.
"""

from pathlib import Path

from memory.coordination import coordination
from memory.coordination.schema import Signal, Task
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

    def post_task(self, description: str, created_by: str, payload: str | None = None) -> str:
        return coordination.post_task(self._conn, description, created_by, payload)

    def claim_task(self, task_id: str, agent: str) -> bool:
        return coordination.claim_task(self._conn, task_id, agent)

    def update_task_status(self, task_id: str, status: str, detail: str | None = None) -> bool:
        """On status in ('completed', 'failed'), also writes a
        reason='task_complete' episode — the same durable-record path
        Atlas._write_episodic already uses for delegated filesystem tasks —
        so blackboard-coordinated work is recorded exactly once, not
        duplicated and not silently dropped when the row is later cleaned up
        (§8 of the design doc)."""
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
        return coordination.get_active_tasks(self._conn, agent_name)

    def send_signal(self, from_agent: str, to_agent: str, payload: str) -> str:
        return coordination.send_signal(self._conn, from_agent, to_agent, payload)

    def get_signals_for(self, agent_name: str) -> list[Signal]:
        return coordination.get_signals_for(self._conn, agent_name)

    def close(self) -> None:
        self._conn.close()

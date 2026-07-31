"""Typed records for the coordination pool, read back out of SQLite by
coordination.py. `memory/coordination/migrations/0001_init.sql` is the source
of truth for column shape; these models are the strict, immutable read
contract on top of it — see docs/HOPE_Coordination_Pool_Design.md for the
schema rationale.
"""

from pydantic import BaseModel, ConfigDict


class Task(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    task_id: str
    description: str
    owner_agent: str | None = None
    status: str  # 'open' | 'claimed' | 'in_progress' | 'completed' | 'failed'
    payload: str | None = None
    created_by: str
    created_at: str
    updated_at: str


class Signal(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    id: str
    from_agent: str
    to_agent: str
    payload: str
    created_at: str
    read_at: str | None = None

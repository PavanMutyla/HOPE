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


class SubAgentRecord(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    agent_id: str
    spoken_name: str
    template: str
    voice_id: str
    status: str  # 'working' | 'idle' | 'failed' | 'retired'
    objective: str
    run_id: str | None = None
    created_at: str
    updated_at: str
    retired_at: str | None = None


class ResearchRun(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    run_id: str
    question: str
    status: str  # 'planning' | 'researching' | 'writing' | 'completed' | 'failed'
    report_path: str | None = None
    summary: str | None = None
    created_at: str
    updated_at: str


class ResearchSource(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    id: int
    run_id: str
    agent_id: str
    url: str
    title: str
    content_hash: str
    fetched_at: str

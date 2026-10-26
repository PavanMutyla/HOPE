"""Typed records for the live session feed, read back out of SQLite by
live.py. `memory/live/migrations/0001_init.sql` is the source of truth for
column shape; these models are the strict, immutable read contract on top of
it — same pattern as memory/board/schema.py.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

# 'idle' is what a dashboard sees when hope.py isn't running (or hasn't spoken
# yet) — distinct from 'listening', which means the pipeline is up and waiting.
LiveState = Literal["idle", "listening", "thinking", "speaking"]


class LiveStatus(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    session_id: str
    agent: str
    state: LiveState
    context_pct: float
    last_tool: str
    started_at: str
    updated_at: str


class LiveTurn(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    seq: int
    role: Literal["user", "assistant"]
    agent: str
    text: str
    ts: str

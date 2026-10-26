"""Typed records for episodic memory, read back out of SQLite by episodic.py.

`memory/episodic_memory/migrations/0001_init.sql` is the source of truth for
column shape; these models are the strict, immutable read/write contract on
top of it — see docs/HOPE_Episodic_Storage_Design.md for the schema
rationale.
"""

from pydantic import BaseModel, ConfigDict, Field


class MediaRef(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    hash: str
    path: str
    mime: str
    size: int


class EpisodeMediaPart(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    seq: int
    kind: str
    mime: str
    media_hash: str | None = None
    path: str | None = None
    external_url: str | None = None


class EpisodeMessage(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    seq: int
    role: str
    content_text: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None
    media: list[EpisodeMediaPart] = Field(default_factory=list)


class Episode(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    id: str
    ts: str
    session_id: str
    agent: str
    reason: str
    span_turns: int
    summary: str
    messages: list[EpisodeMessage] = Field(default_factory=list)


class Plan(BaseModel):
    """Unlike Episode, this is mutated in place as it resolves — not an
    immutable log entry. See migrations/0002_add_plans.sql."""

    model_config = ConfigDict(strict=True, frozen=True)

    id: str
    agent: str
    description: str
    status: str  # 'pending' | 'completed' | 'abandoned' | 'superseded'
    created_at: str
    resolved_at: str | None = None
    resulting_episode_id: str | None = None
    superseded_by: str | None = None


class Session(BaseModel):
    """One conversation, rolled up from every episode sharing a session_id.

    Not a table — there is no `sessions` table and deliberately so. A session
    is whatever `session_id` groups together, and that id is minted per
    `hope.py` run (`core/voice/pipeline.py`), so "one session" means "one time
    Pavan sat down and talked to HOPE." Computed by
    `episodic.list_sessions()`, never written.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    session_id: str
    agent: str
    started_at: str
    ended_at: str
    episode_count: int
    message_count: int
    summary: str  # from the session's most recent episode

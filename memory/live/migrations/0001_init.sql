-- Live session feed — what HOPE is doing *right now*, written by the running
-- pipeline and read by the dashboard process. Applied by
-- memory/live/live.py:connect(). Idempotent, like every other migration here.
--
-- This is the only cross-process channel out of hope.py's pipeline. It exists
-- because the dashboard is a separate OS process and cannot see the pipeline's
-- in-memory state (LLMContext, StatusPanel, agent_state).
--
-- Deliberately transient: live_turns is cleared at the start of each run. The
-- durable record of a conversation is episodic memory, written at fold and at
-- session close. Nothing here is a source of truth, and losing the file costs
-- nothing but the current session's live view.

-- Singleton row (id always 1) — the current pipeline state, overwritten in
-- place rather than appended, because only the latest value is ever read.
CREATE TABLE IF NOT EXISTS live_state (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    session_id    TEXT NOT NULL DEFAULT '',
    agent         TEXT NOT NULL DEFAULT '',
    state         TEXT NOT NULL DEFAULT 'idle',  -- idle|listening|thinking|speaking
    context_pct   REAL NOT NULL DEFAULT 0.0,
    last_tool     TEXT NOT NULL DEFAULT '',
    started_at    TEXT NOT NULL DEFAULT '',
    updated_at    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS live_turns (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    seq           INTEGER NOT NULL,
    role          TEXT NOT NULL,   -- 'user' | 'assistant'
    agent         TEXT NOT NULL,   -- which agent spoke; '' for user turns
    text          TEXT NOT NULL,
    ts            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_live_turns_session ON live_turns(session_id, seq);

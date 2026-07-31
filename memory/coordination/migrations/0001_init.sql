-- Coordination pool schema — the blackboard. See
-- docs/HOPE_Coordination_Pool_Design.md for the rationale (live, mutable,
-- shared state for in-flight coordination; not a duplicate of episodic
-- memory, which only ever records what already happened).
--
-- Applied by memory/coordination/coordination.py:connect(). All statements
-- are idempotent (IF NOT EXISTS) so re-running this file on an existing
-- database is always safe.

CREATE TABLE IF NOT EXISTS tasks (
    task_id       TEXT PRIMARY KEY,     -- ULID, prefixed "task_"
    description   TEXT NOT NULL,
    owner_agent   TEXT,                 -- NULL until claimed
    status        TEXT NOT NULL,        -- 'open' | 'claimed' | 'in_progress' | 'completed' | 'failed'
    payload       TEXT,                 -- JSON, task-specific detail (free-form)
    created_by    TEXT NOT NULL,        -- agent that posted the task
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_owner  ON tasks(owner_agent);

CREATE TABLE IF NOT EXISTS signals (
    id            TEXT PRIMARY KEY,     -- ULID, prefixed "sig_"
    from_agent    TEXT NOT NULL,
    to_agent      TEXT NOT NULL,        -- point-to-point only, no broadcast in v1
    payload       TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    read_at       TEXT                  -- NULL until the recipient consumes it
);

CREATE INDEX IF NOT EXISTS idx_signals_to_unread ON signals(to_agent, read_at);

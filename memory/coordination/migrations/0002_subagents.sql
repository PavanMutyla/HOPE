-- Dynamically spawned sub-agents and the deep-research runs they work on.
-- See docs/HOPE_Dynamic_SubAgents_Research.md §DB.
--
-- Lives in the blackboard, not a new database file: this is live, mutable
-- coordination state (who exists right now, what they're doing), and the
-- dashboard already reads this file. Sub-agents never touch it themselves —
-- every write goes through the runner code, never through an LLM tool.

CREATE TABLE IF NOT EXISTS agents (
    agent_id      TEXT PRIMARY KEY,     -- ULID, prefixed "agt_"
    spoken_name   TEXT NOT NULL,        -- what Pavan says out loud ("Emma")
    template      TEXT NOT NULL,        -- 'researcher' | ...
    voice_id      TEXT NOT NULL,        -- Kokoro voice, leased from VoicePool
    status        TEXT NOT NULL,        -- 'working' | 'idle' | 'failed' | 'retired'
    objective     TEXT NOT NULL,
    run_id        TEXT,                 -- research_runs.run_id, if part of one
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    retired_at    TEXT
);

-- Disposable-per-run agents: whatever isn't retired belongs to the current
-- hope.py process. A row still live at startup is a leftover from a run that
-- was killed, and gets retired (which also frees its voice).
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);

CREATE TABLE IF NOT EXISTS research_runs (
    run_id        TEXT PRIMARY KEY,     -- ULID, prefixed "run_"
    question      TEXT NOT NULL,
    status        TEXT NOT NULL,        -- 'planning' | 'researching' | 'writing' | 'completed' | 'failed'
    report_path   TEXT,                 -- data_store/research/<run_id>/report.md once written
    summary       TEXT,                 -- the short spoken version
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

-- One row per page a researcher actually read. Page text itself is stored
-- on disk, content-addressed by content_hash (same idea as episodic media),
-- so the same page read by two researchers is stored once.
CREATE TABLE IF NOT EXISTS research_sources (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    agent_id      TEXT NOT NULL,
    url           TEXT NOT NULL,
    title         TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    fetched_at    TEXT NOT NULL,
    UNIQUE (run_id, agent_id, url)
);

CREATE INDEX IF NOT EXISTS idx_research_sources_run ON research_sources(run_id);

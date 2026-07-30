-- Plan tracking — a plan is written down when formed (before anything
-- happens), unlike the episodes table where every row is retrospective.
-- Deliberately a separate table, not a new `episodes.reason` value: a plan
-- is mutated in place as it resolves (status changes), whereas episodes are
-- immutable once written (aside from the raw -> upgraded summary swap).
-- See docs/HOPE_Shared_Team_Memory_Research.md.
--
-- Applied by memory/episodic_memory/episodic.py:connect(). All statements
-- are idempotent (IF NOT EXISTS) so re-running this file on an existing
-- database is always safe.

CREATE TABLE IF NOT EXISTS plans (
    id                   TEXT PRIMARY KEY,   -- ULID, prefixed "plan_"
    agent                TEXT NOT NULL,
    description          TEXT NOT NULL,      -- the intention/task as stated when the plan was formed
    status               TEXT NOT NULL,      -- 'pending' | 'completed' | 'abandoned' | 'superseded'
    created_at           TEXT NOT NULL,
    resolved_at          TEXT,               -- set when status leaves 'pending'
    resulting_episode_id TEXT REFERENCES episodes(id),  -- set only on 'completed'
    superseded_by        TEXT REFERENCES plans(id)      -- set only on 'superseded'
);

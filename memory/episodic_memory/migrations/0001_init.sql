-- Episodic memory schema — see docs/HOPE_Episodic_Storage_Design.md for the
-- rationale (normalized tables instead of a single JSON/JSONL blob per
-- entry, so media dedupes by content hash and structured queries work).
--
-- Applied by memory/episodic_memory/episodic.py:connect(). All statements
-- are idempotent (IF NOT EXISTS) so re-running this file on an existing
-- database is always safe.

CREATE TABLE IF NOT EXISTS episodes (
    id            TEXT PRIMARY KEY,   -- ULID, prefixed "ep_"
    ts            TEXT NOT NULL,
    session_id    TEXT NOT NULL,
    agent         TEXT NOT NULL,
    reason        TEXT NOT NULL,      -- 'threshold' | 'session_end_raw' | 'session_end'
    span_turns    INTEGER NOT NULL,
    summary       TEXT NOT NULL       -- embedding target; == raw text for a trivial-tail flush
);

CREATE TABLE IF NOT EXISTS episode_messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id    TEXT NOT NULL REFERENCES episodes(id),
    seq           INTEGER NOT NULL,   -- order within the episode
    role          TEXT NOT NULL,      -- user | assistant | tool | system
    content_text  TEXT,               -- concatenated text parts; NULL if pure media
    tool_call_id  TEXT,
    tool_calls    TEXT                -- JSON, only present on assistant tool-call messages
);

CREATE TABLE IF NOT EXISTS media (
    hash          TEXT PRIMARY KEY,   -- sha256 of raw bytes
    path          TEXT NOT NULL,      -- data_store/episodic_memory/media/<hash[:2]>/<hash>
    mime          TEXT NOT NULL,
    size          INTEGER NOT NULL,
    first_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episode_media (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id    INTEGER NOT NULL REFERENCES episode_messages(id),
    seq           INTEGER NOT NULL,   -- part order within the message
    media_hash    TEXT REFERENCES media(hash),  -- NULL if external_url is set instead
    external_url  TEXT,
    mime          TEXT NOT NULL,
    kind          TEXT NOT NULL       -- 'image' | 'audio' (future)
);

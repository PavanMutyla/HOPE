-- Shared board schema — Today/Planned/Pending task lists + a single shared
-- Quick notes blob, common to every agent (and Pavan, editing from the
-- dashboard). Applied by memory/board/board.py:connect(). All statements are
-- idempotent (IF NOT EXISTS) so re-running this file on an existing database
-- is always safe.

CREATE TABLE IF NOT EXISTS board_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    list_type     TEXT NOT NULL CHECK (list_type IN ('today', 'planned', 'pending')),
    text          TEXT NOT NULL,
    done          INTEGER NOT NULL DEFAULT 0,
    agent         TEXT NOT NULL,        -- who last touched this item (created/edited/toggled)
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_board_items_list_type ON board_items(list_type);

-- Singleton row (id always 1) — Quick notes stays one shared blob, not
-- per-entry, per design decision.
CREATE TABLE IF NOT EXISTS quick_note (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    content       TEXT NOT NULL DEFAULT '',
    agent         TEXT NOT NULL DEFAULT '',
    updated_at    TEXT NOT NULL
);

"""SQLite layer for the shared board — Today/Planned/Pending task lists plus
a single shared Quick notes blob, common to every agent. Same connection and
migration pattern as memory/coordination/coordination.py.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from memory.board.schema import BoardItem, ListType, QuickNote

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Runs every .sql file under migrations/ in order. Each migration's
    statements are idempotent (CREATE TABLE IF NOT EXISTS), so replaying all
    of them on an already-migrated database is always safe."""
    for migration in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(migration.read_text())


def connect(db_path: Path) -> sqlite3.Connection:
    """`check_same_thread=False` + WAL + busy_timeout, same as
    memory/coordination/coordination.py:connect() — required from the start
    since multiple processes (hope.py, the dashboard, Atlas's own tool
    dispatch) all write to this same file concurrently."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    _apply_migrations(conn)
    return conn


def _row_to_item(row: sqlite3.Row) -> BoardItem:
    return BoardItem(
        id=row["id"],
        list_type=row["list_type"],
        text=row["text"],
        done=bool(row["done"]),
        agent=row["agent"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def add_item(conn: sqlite3.Connection, list_type: ListType, text: str, agent: str) -> BoardItem:
    ts = _now_iso()
    with conn:
        cur = conn.execute(
            "INSERT INTO board_items (list_type, text, done, agent, created_at, updated_at) "
            "VALUES (?, ?, 0, ?, ?, ?)",
            (list_type, text, agent, ts, ts),
        )
    return BoardItem(
        id=cur.lastrowid, list_type=list_type, text=text, done=False,
        agent=agent, created_at=ts, updated_at=ts,
    )


def update_item_text(
    conn: sqlite3.Connection, item_id: int, text: str, agent: str
) -> BoardItem | None:
    ts = _now_iso()
    with conn:
        cur = conn.execute(
            "UPDATE board_items SET text = ?, agent = ?, updated_at = ? WHERE id = ?",
            (text, agent, ts, item_id),
        )
        if cur.rowcount == 0:
            return None
    return get_item(conn, item_id)


def toggle_item(conn: sqlite3.Connection, item_id: int, agent: str) -> BoardItem | None:
    """Toggling is also a touch — stamps `agent` with whoever flipped it,
    same as a text edit, per the board's single last-touched-by field."""
    ts = _now_iso()
    with conn:
        cur = conn.execute(
            "UPDATE board_items SET done = NOT done, agent = ?, updated_at = ? WHERE id = ?",
            (agent, ts, item_id),
        )
        if cur.rowcount == 0:
            return None
    return get_item(conn, item_id)


def delete_item(conn: sqlite3.Connection, item_id: int) -> bool:
    with conn:
        cur = conn.execute("DELETE FROM board_items WHERE id = ?", (item_id,))
    return cur.rowcount == 1


def get_item(conn: sqlite3.Connection, item_id: int) -> BoardItem | None:
    row = conn.execute("SELECT * FROM board_items WHERE id = ?", (item_id,)).fetchone()
    return _row_to_item(row) if row else None


def list_items(conn: sqlite3.Connection, list_type: ListType) -> list[BoardItem]:
    rows = conn.execute(
        "SELECT * FROM board_items WHERE list_type = ? ORDER BY created_at", (list_type,)
    ).fetchall()
    return [_row_to_item(row) for row in rows]


def get_quick_note(conn: sqlite3.Connection) -> QuickNote:
    row = conn.execute("SELECT * FROM quick_note WHERE id = 1").fetchone()
    if row is None:
        return QuickNote(content="", agent="", updated_at=_now_iso())
    return QuickNote(content=row["content"], agent=row["agent"], updated_at=row["updated_at"])


def update_quick_note(conn: sqlite3.Connection, content: str, agent: str) -> QuickNote:
    ts = _now_iso()
    with conn:
        conn.execute(
            "INSERT INTO quick_note (id, content, agent, updated_at) VALUES (1, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET content = excluded.content, "
            "agent = excluded.agent, updated_at = excluded.updated_at",
            (content, agent, ts),
        )
    return QuickNote(content=content, agent=agent, updated_at=ts)

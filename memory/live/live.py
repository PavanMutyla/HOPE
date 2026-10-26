"""SQLite layer for the live session feed. Same connection and migration
pattern as memory/board/board.py.

Writes come from the running pipeline (one process, one thread); reads come
from the dashboard (a different process). WAL makes that safe without either
side coordinating with the other.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from memory.live.schema import LiveStatus, LiveTurn

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_EMPTY_STATUS = LiveStatus(
    session_id="", agent="", state="idle", context_pct=0.0,
    last_tool="", started_at="", updated_at="",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for migration in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(migration.read_text())


def connect(db_path: Path) -> sqlite3.Connection:
    """`check_same_thread=False` + WAL + busy_timeout, same as
    memory/board/board.py:connect() — the pipeline writes from its event loop
    while the dashboard process reads on its own."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    _apply_migrations(conn)
    return conn


def start_session(conn: sqlite3.Connection, session_id: str, agent: str) -> None:
    """Begin a run: clear the previous run's turns and reset the status row.

    Clearing is the point — live_turns is a window onto the *current*
    conversation, and the durable copy of the last one already went to
    episodic memory at session close. Keeping old turns around would make a
    dead session look live in the dashboard.
    """
    ts = _now_iso()
    with conn:
        conn.execute("DELETE FROM live_turns")
        conn.execute(
            "INSERT INTO live_state (id, session_id, agent, state, context_pct, "
            "last_tool, started_at, updated_at) VALUES (1, ?, ?, 'listening', 0.0, '', ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "session_id = excluded.session_id, agent = excluded.agent, "
            "state = 'listening', context_pct = 0.0, last_tool = '', "
            "started_at = excluded.started_at, updated_at = excluded.updated_at",
            (session_id, agent, ts, ts),
        )


def end_session(conn: sqlite3.Connection) -> None:
    """Mark the pipeline down. Turns are deliberately left in place so the
    dashboard still shows the conversation that just finished, until the next
    run clears them — a blank panel the moment HOPE exits would look broken."""
    with conn:
        conn.execute(
            "UPDATE live_state SET state = 'idle', updated_at = ? WHERE id = 1",
            (_now_iso(),),
        )


def heartbeat(conn: sqlite3.Connection) -> None:
    """Touch updated_at without changing anything else.

    end_session() only runs on a clean shutdown. A kill -9, a crash or a lost
    power cable leaves state='listening' in the row forever, and the dashboard
    would show a green "HOPE is live" indicator for a process that no longer
    exists. A periodic heartbeat plus a staleness check on the reader is what
    makes absence detectable: state says what HOPE was doing, updated_at says
    whether anyone is still there to do it.

    A heartbeat is needed rather than just relying on frame traffic, because a
    genuinely-running HOPE waiting in silence produces no frames at all.
    """
    with conn:
        conn.execute(
            "UPDATE live_state SET updated_at = ? WHERE id = 1", (_now_iso(),)
        )


def set_state(conn: sqlite3.Connection, state: str) -> None:
    with conn:
        conn.execute(
            "UPDATE live_state SET state = ?, updated_at = ? WHERE id = 1",
            (state, _now_iso()),
        )


def set_agent(conn: sqlite3.Connection, agent: str) -> None:
    with conn:
        conn.execute(
            "UPDATE live_state SET agent = ?, updated_at = ? WHERE id = 1",
            (agent, _now_iso()),
        )


def set_context_pct(conn: sqlite3.Connection, context_pct: float) -> None:
    with conn:
        conn.execute(
            "UPDATE live_state SET context_pct = ?, updated_at = ? WHERE id = 1",
            (context_pct, _now_iso()),
        )


def set_last_tool(conn: sqlite3.Connection, tool: str) -> None:
    with conn:
        conn.execute(
            "UPDATE live_state SET last_tool = ?, updated_at = ? WHERE id = 1",
            (tool, _now_iso()),
        )


def append_turn(
    conn: sqlite3.Connection, session_id: str, role: str, agent: str, text: str
) -> int:
    """Append one finished turn. `seq` is assigned here rather than by the
    caller so two writers can't collide on it."""
    with conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 AS next FROM live_turns WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        seq = row["next"]
        conn.execute(
            "INSERT INTO live_turns (session_id, seq, role, agent, text, ts) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, seq, role, agent, text, _now_iso()),
        )
    return seq


def get_status(conn: sqlite3.Connection) -> LiveStatus:
    """Never None — an unwritten feed reads as idle, so the dashboard renders
    'HOPE is not running' rather than having to special-case a missing row."""
    row = conn.execute("SELECT * FROM live_state WHERE id = 1").fetchone()
    if row is None:
        return _EMPTY_STATUS
    return LiveStatus(
        session_id=row["session_id"],
        agent=row["agent"],
        state=row["state"],
        context_pct=row["context_pct"],
        last_tool=row["last_tool"],
        started_at=row["started_at"],
        updated_at=row["updated_at"],
    )


def get_turns(conn: sqlite3.Connection, session_id: str, limit: int = 100) -> list[LiveTurn]:
    """Most recent `limit` turns, returned oldest-first for rendering."""
    rows = conn.execute(
        "SELECT seq, role, agent, text, ts FROM live_turns WHERE session_id = ? "
        "ORDER BY seq DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    return [
        LiveTurn(seq=r["seq"], role=r["role"], agent=r["agent"], text=r["text"], ts=r["ts"])
        for r in reversed(rows)
    ]

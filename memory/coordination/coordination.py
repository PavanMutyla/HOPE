"""SQLite layer for the coordination pool — the blackboard. See
docs/HOPE_Coordination_Pool_Design.md for the schema rationale (live,
mutable, shared state for in-flight coordination between concurrent agents;
episodic memory remains the durable record of what already happened).
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ulid import ULID

from memory.coordination.schema import Signal, Task

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Runs every .sql file under migrations/ in order. Each migration's
    statements are idempotent (CREATE TABLE IF NOT EXISTS), so replaying all
    of them on an already-migrated database is always safe — no separate
    applied-migrations tracking table needed while there's a single file."""
    for migration in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(migration.read_text())


def connect(db_path: Path) -> sqlite3.Connection:
    """`check_same_thread=False` + WAL + busy_timeout, same as
    memory/episodic_memory/episodic.py:connect() — required from the start
    here (not retrofitted after a bug) because concurrent agents writing to
    the same file is the entire premise of this tier, not an edge case."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    _apply_migrations(conn)
    return conn


def post_task(
    conn: sqlite3.Connection,
    description: str,
    created_by: str,
    payload: str | None = None,
    ts: str | None = None,
) -> str:
    task_id = f"task_{ULID()}"
    ts = ts or _now_iso()
    with conn:
        conn.execute(
            "INSERT INTO tasks (task_id, description, owner_agent, status, payload, "
            "created_by, created_at, updated_at) VALUES (?, ?, NULL, 'open', ?, ?, ?, ?)",
            (task_id, description, payload, created_by, ts, ts),
        )
    return task_id


def claim_task(conn: sqlite3.Connection, task_id: str, agent: str) -> bool:
    """Two agents racing to claim the same task is the concrete failure this
    tier exists to prevent. A single conditional UPDATE is sufficient —
    SQLite serializes writes to one file, so there's no window for two claims
    to both 'succeed'. `rowcount == 1` means this call won the claim; `0`
    means someone else already did (or the task doesn't exist) — the caller
    treats that as a normal negative result, not an error."""
    with conn:
        cur = conn.execute(
            "UPDATE tasks SET owner_agent = ?, status = 'claimed', updated_at = ? "
            "WHERE task_id = ? AND owner_agent IS NULL",
            (agent, _now_iso(), task_id),
        )
    return cur.rowcount == 1


def update_task_status(
    conn: sqlite3.Connection, task_id: str, status: str, detail: str | None = None
) -> bool:
    """Returns False if task_id doesn't exist, True otherwise. `detail`, when
    given, overwrites `payload` — the caller (Blackboard facade) is
    responsible for triggering the episodic task_complete write when status
    lands on 'completed' or 'failed'."""
    ts = _now_iso()
    with conn:
        if detail is not None:
            cur = conn.execute(
                "UPDATE tasks SET status = ?, payload = ?, updated_at = ? WHERE task_id = ?",
                (status, detail, ts, task_id),
            )
        else:
            cur = conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                (status, ts, task_id),
            )
    return cur.rowcount == 1


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        task_id=row["task_id"],
        description=row["description"],
        owner_agent=row["owner_agent"],
        status=row["status"],
        payload=row["payload"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_task(conn: sqlite3.Connection, task_id: str) -> Task | None:
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    return _row_to_task(row) if row else None


def get_active_tasks(conn: sqlite3.Connection, agent_name: str | None = None) -> list[Task]:
    """Active == status in ('open', 'claimed', 'in_progress'). With
    agent_name, further filtered to tasks owned by that agent; without it,
    every active task regardless of owner."""
    query = "SELECT * FROM tasks WHERE status IN ('open', 'claimed', 'in_progress')"
    params: list[str] = []
    if agent_name is not None:
        query += " AND owner_agent = ?"
        params.append(agent_name)
    query += " ORDER BY created_at"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_task(row) for row in rows]


def send_signal(
    conn: sqlite3.Connection,
    from_agent: str,
    to_agent: str,
    payload: str,
    ts: str | None = None,
) -> str:
    signal_id = f"sig_{ULID()}"
    ts = ts or _now_iso()
    with conn:
        conn.execute(
            "INSERT INTO signals (id, from_agent, to_agent, payload, created_at, read_at) "
            "VALUES (?, ?, ?, ?, ?, NULL)",
            (signal_id, from_agent, to_agent, payload, ts),
        )
    return signal_id


def get_signals_for(conn: sqlite3.Connection, agent_name: str) -> list[Signal]:
    """Returns unread signals addressed to agent_name, oldest first, and
    marks them read (read_at set) as part of the same call — retrieval is
    consumption, matching the design's polling model (§6/§7)."""
    with conn:
        rows = conn.execute(
            "SELECT * FROM signals WHERE to_agent = ? AND read_at IS NULL ORDER BY created_at",
            (agent_name,),
        ).fetchall()
        signals = [
            Signal(
                id=row["id"],
                from_agent=row["from_agent"],
                to_agent=row["to_agent"],
                payload=row["payload"],
                created_at=row["created_at"],
                read_at=None,
            )
            for row in rows
        ]
        if signals:
            ts = _now_iso()
            conn.executemany(
                "UPDATE signals SET read_at = ? WHERE id = ?",
                [(ts, signal.id) for signal in signals],
            )
    return signals

"""SQLite layer for plan tracking — see migrations/0002_add_plans.sql for
the schema rationale. Lives alongside episodic.py (same connection, same
database) since a plan's whole point is to eventually link to the episode
that records what actually happened.
"""

import sqlite3
from datetime import datetime, timezone

from ulid import ULID

from memory.episodic_memory.schema import Plan


def create_plan(
    conn: sqlite3.Connection, agent: str, description: str, ts: str | None = None
) -> str:
    plan_id = f"plan_{ULID()}"
    ts = ts or datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            "INSERT INTO plans (id, agent, description, status, created_at) "
            "VALUES (?, ?, ?, 'pending', ?)",
            (plan_id, agent, description, ts),
        )
    return plan_id


def resolve_plan(conn: sqlite3.Connection, plan_id: str, resulting_episode_id: str) -> None:
    with conn:
        conn.execute(
            "UPDATE plans SET status = 'completed', resolved_at = ?, resulting_episode_id = ? "
            "WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), resulting_episode_id, plan_id),
        )


def abandon_plan(conn: sqlite3.Connection, plan_id: str) -> None:
    with conn:
        conn.execute(
            "UPDATE plans SET status = 'abandoned', resolved_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), plan_id),
        )


def supersede_plan(conn: sqlite3.Connection, plan_id: str, superseded_by: str) -> None:
    with conn:
        conn.execute(
            "UPDATE plans SET status = 'superseded', resolved_at = ?, superseded_by = ? "
            "WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), superseded_by, plan_id),
        )


def _row_to_plan(row: sqlite3.Row) -> Plan:
    return Plan(
        id=row["id"],
        agent=row["agent"],
        description=row["description"],
        status=row["status"],
        created_at=row["created_at"],
        resolved_at=row["resolved_at"],
        resulting_episode_id=row["resulting_episode_id"],
        superseded_by=row["superseded_by"],
    )


def get_plan(conn: sqlite3.Connection, plan_id: str) -> Plan | None:
    row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    return _row_to_plan(row) if row else None


def list_plans(
    conn: sqlite3.Connection, agent: str | None = None, status: str | None = None
) -> list[Plan]:
    query = "SELECT * FROM plans"
    conditions = []
    params: list[str] = []
    if agent is not None:
        conditions.append("agent = ?")
        params.append(agent)
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_plan(row) for row in rows]

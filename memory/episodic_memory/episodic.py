"""SQLite layer for episodic memory — the source of truth for every folded
episode, including multimodal content. See docs/HOPE_Episodic_Storage_Design.md
for the schema rationale (normalized tables instead of a single JSON/JSONL
blob, so media dedupes and structured queries are possible).

Raw OpenAI-style chat messages are normalized on write:
  - `content` as a plain string -> `episode_messages.content_text`
  - `content` as a list of parts (multimodal) -> text parts join into
    `content_text`; `image_url` parts become `episode_media` rows, with the
    bytes handed to `media.store_bytes()` when inline (`data:` URI) or kept
    as a bare reference (`external_url`) when the part points at a remote URL.
"""

import base64
import json
import mimetypes
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ulid import ULID

from memory.episodic_memory.media import store_bytes
from memory.episodic_memory.schema import Episode, EpisodeMediaPart, EpisodeMessage

_DATA_URI_RE = re.compile(r"^data:(?P<mime>[^;,]+);base64,(?P<data>.+)$", re.DOTALL)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Runs every .sql file under migrations/ in order. Each migration's
    statements are idempotent (CREATE TABLE IF NOT EXISTS), so replaying all
    of them on an already-migrated database is always safe — no separate
    applied-migrations tracking table needed while there's a single file."""
    for migration in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(migration.read_text())


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(conn)
    return conn


def _split_data_uri(url: str) -> tuple[str, bytes] | None:
    match = _DATA_URI_RE.match(url)
    if not match:
        return None
    return match.group("mime"), base64.b64decode(match.group("data"))


def _extract_parts(content) -> tuple[str | None, list[dict]]:
    """Split a raw `content` value into (content_text, media_parts).

    `media_parts` are `{"kind": ..., "url": ...}` dicts in original order —
    not yet resolved to disk/db, since that requires the media_dir + episode
    context that only `create_episode` has.
    """
    if content is None:
        return None, []
    if isinstance(content, str):
        return content, []
    text_parts = []
    media_parts = []
    for part in content:
        if not isinstance(part, dict):
            continue
        ptype = part.get("type")
        if ptype == "text":
            text_parts.append(part.get("text", ""))
        elif ptype == "image_url":
            url = part.get("image_url", {}).get("url", "")
            media_parts.append({"kind": "image", "url": url})
    content_text = "\n".join(text_parts) if text_parts else None
    return content_text, media_parts


def create_episode(
    conn: sqlite3.Connection,
    media_dir: Path,
    agent: str,
    session_id: str,
    reason: str,
    span_turns: int,
    summary: str,
    messages: list[dict],
    ts: str | None = None,
) -> str:
    """Normalize and persist one episodic entry. Returns the new episode id."""
    episode_id = f"ep_{ULID()}"
    ts = ts or datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            "INSERT INTO episodes (id, ts, session_id, agent, reason, span_turns, summary) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (episode_id, ts, session_id, agent, reason, span_turns, summary),
        )
        for seq, message in enumerate(messages):
            content_text, media_parts = _extract_parts(message.get("content"))
            tool_calls = message.get("tool_calls")
            cursor = conn.execute(
                "INSERT INTO episode_messages "
                "(episode_id, seq, role, content_text, tool_call_id, tool_calls) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    episode_id,
                    seq,
                    message.get("role", "?"),
                    content_text,
                    message.get("tool_call_id"),
                    json.dumps(tool_calls) if tool_calls else None,
                ),
            )
            message_id = cursor.lastrowid
            for media_seq, media_part in enumerate(media_parts):
                _insert_media_part(conn, media_dir, message_id, media_seq, media_part, ts)
    return episode_id


def _insert_media_part(
    conn: sqlite3.Connection,
    media_dir: Path,
    message_id: int,
    seq: int,
    media_part: dict,
    ts: str,
) -> None:
    url = media_part["url"]
    kind = media_part["kind"]
    decoded = _split_data_uri(url)
    if decoded is not None:
        mime, data = decoded
        ref = store_bytes(data, mime, media_dir)
        conn.execute(
            "INSERT OR IGNORE INTO media (hash, path, mime, size, first_seen_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (ref.hash, ref.path, ref.mime, ref.size, ts),
        )
        conn.execute(
            "INSERT INTO episode_media (message_id, seq, media_hash, external_url, mime, kind) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, seq, ref.hash, None, ref.mime, kind),
        )
    else:
        mime = mimetypes.guess_type(url)[0] or "application/octet-stream"
        conn.execute(
            "INSERT INTO episode_media (message_id, seq, media_hash, external_url, mime, kind) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, seq, None, url, mime, kind),
        )


def get_episode(conn: sqlite3.Connection, episode_id: str) -> Episode | None:
    """Hydrate one full episode — messages and their media parts, in order."""
    episode_row = conn.execute(
        "SELECT * FROM episodes WHERE id = ?", (episode_id,)
    ).fetchone()
    if episode_row is None:
        return None

    message_rows = conn.execute(
        "SELECT * FROM episode_messages WHERE episode_id = ? ORDER BY seq",
        (episode_id,),
    ).fetchall()

    messages = []
    for message_row in message_rows:
        media_rows = conn.execute(
            "SELECT em.seq, em.kind, em.mime, em.media_hash, em.external_url, m.path "
            "FROM episode_media em LEFT JOIN media m ON m.hash = em.media_hash "
            "WHERE em.message_id = ? ORDER BY em.seq",
            (message_row["id"],),
        ).fetchall()
        media = [
            EpisodeMediaPart(
                seq=row["seq"],
                kind=row["kind"],
                mime=row["mime"],
                media_hash=row["media_hash"],
                path=row["path"],
                external_url=row["external_url"],
            )
            for row in media_rows
        ]
        tool_calls = json.loads(message_row["tool_calls"]) if message_row["tool_calls"] else None
        messages.append(
            EpisodeMessage(
                seq=message_row["seq"],
                role=message_row["role"],
                content_text=message_row["content_text"],
                tool_call_id=message_row["tool_call_id"],
                tool_calls=tool_calls,
                media=media,
            )
        )

    return Episode(
        id=episode_row["id"],
        ts=episode_row["ts"],
        session_id=episode_row["session_id"],
        agent=episode_row["agent"],
        reason=episode_row["reason"],
        span_turns=episode_row["span_turns"],
        summary=episode_row["summary"],
        messages=messages,
    )

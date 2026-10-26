"""LiveFeed facade — the single entry point for the live session feed.

Writers: the pipeline's LiveFeedObserver (core/voice/live_feed.py) and
hope.py's startup/shutdown. Reader: the dashboard process.
"""

from pathlib import Path

from memory.live import live
from memory.live.schema import LiveStatus, LiveTurn
from settings import settings


class LiveFeed:
    def __init__(self, db_path: str | Path | None = None):
        self._conn = live.connect(db_path or settings.live_db_path)

    def start_session(self, session_id: str, agent: str) -> None:
        live.start_session(self._conn, session_id, agent)

    def end_session(self) -> None:
        live.end_session(self._conn)

    def heartbeat(self) -> None:
        live.heartbeat(self._conn)

    def set_state(self, state: str) -> None:
        live.set_state(self._conn, state)

    def set_agent(self, agent: str) -> None:
        live.set_agent(self._conn, agent)

    def set_context_pct(self, context_pct: float) -> None:
        live.set_context_pct(self._conn, context_pct)

    def set_last_tool(self, tool: str) -> None:
        live.set_last_tool(self._conn, tool)

    def append_turn(self, session_id: str, role: str, agent: str, text: str) -> int:
        return live.append_turn(self._conn, session_id, role, agent, text)

    def get_status(self) -> LiveStatus:
        return live.get_status(self._conn)

    def get_turns(self, session_id: str, limit: int = 100) -> list[LiveTurn]:
        return live.get_turns(self._conn, session_id, limit)

    def close(self) -> None:
        self._conn.close()

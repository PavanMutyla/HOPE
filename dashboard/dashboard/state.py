"""Dashboard state.

Two sources feed this, both SQLite over WAL, because the dashboard is a
separate OS process from hope.py and cannot see the pipeline's in-memory state:

- the **shared board** (memory/board/) backs the corkboard notes, the same rows
  HOPE and Atlas edit by voice;
- **episodic memory** (past conversations) and the **live feed**
  (memory/live/, written by the running pipeline) back the console.

There is no text input anywhere. HOPE takes voice only, so the console reads
rather than writes: it shows the conversation happening now, or one that
already happened.
"""

import dashboard._pathfix  # noqa: F401 — sys.path side effect, must run first

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path

import reflex as rx

from dashboard.data import NOTE_LAYOUT
from memory.board import live as board_live
from memory.board.store import Board
from memory.episodic_memory.store import EpisodicMemory
from memory.live.store import LiveFeed
from settings import settings

_board = Board()
_episodic = EpisodicMemory()
_live = LiveFeed()

_BOARD_REFRESH_SECONDS = 15
_LOG_REFRESH_SECONDS = 3
_LIVE_REFRESH_SECONDS = 1  # the live console is the one thing that should feel immediate
_SESSION_REFRESH_SECONDS = 30
# How long the live row may go untouched before the writer is presumed
# gone. hope.py heartbeats every 10s, so 30s is three missed beats; short
# enough that a crashed pipeline stops claiming to be live almost at once,
# long enough to ride out a slow fold or a GC pause.
_LIVE_STALE_SECONDS = 30
_LOG_TAIL_LINES = 200

# The Tools and Web cards are filters over the same hope.log the Log card
# tails, keyed on the tags hope.py's code writes: "[tool]" from
# tools/registry.py and Atlas, and the internet tags from deep research, the
# sub-agent manager, HOPE's own search/read tools and the degoog service.
_TOOL_TAGS = ("[tool] ",)
_WEB_TAGS = ("[research] ", "[agents] ", "[web] ", "[degoog] ")
# Loguru's default line: "2026-10-26 23:55:28.835 | INFO     | module:fn:12 - message".
_LOGURU_LINE = re.compile(r"^\d{4}-\d\d-\d\d (\d\d:\d\d:\d\d)\.\d+ \| (\w+)\s*\| \S+ - (.*)$")

# The marker ContextSummarizer.flush() writes for a session archived raw at
# shutdown and not yet re-summarized. Showing it verbatim leaks an internal
# detail into the thread list, so it gets replaced with plain language.
_UNSUMMARIZED = "[NOT SUMMARIZED YET"

# Warm-start injection and the greeting prompt are written as `developer`
# messages. They are scaffolding the pipeline sends itself, not things anyone
# said, so the transcript hides them.
_VISIBLE_ROLES = ("user", "assistant")

LIVE_THREAD_ID = "__live__"


def _relative_time(iso_ts: str) -> str:
    """'4m', '2h', '3d'. Absolute dates are shown alongside, so this only has
    to convey recency at a glance."""
    if not iso_ts:
        return ""
    try:
        then = datetime.fromisoformat(iso_ts)
    except ValueError:
        return ""
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    seconds = (datetime.now(timezone.utc) - then).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"


def _is_stale(iso_ts: str) -> bool:
    """True when the live row has not been heartbeated recently enough to
    believe. An unparseable or empty timestamp counts as stale: it means
    nothing has ever written the row."""
    if not iso_ts:
        return True
    try:
        then = datetime.fromisoformat(iso_ts)
    except ValueError:
        return True
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds() > _LIVE_STALE_SECONDS


def _day_label(iso_ts: str) -> str:
    if not iso_ts:
        return ""
    try:
        then = datetime.fromisoformat(iso_ts)
    except ValueError:
        return ""
    return then.strftime("%-d %b, %-I:%M %p")


def _activity_rows(lines: list[str], tags: tuple[str, ...]) -> list[dict]:
    """Lines carrying one of `tags`, reduced to a time and a readable message.
    The tag itself is dropped since the card names it, except degoog's, which
    would otherwise read as an unattributed "Ready on 127.0.0.1:4444"."""
    rows = []
    for line in lines:
        match = _LOGURU_LINE.match(line)
        if not match:
            continue
        time, level, message = match.groups()
        tag = next((t for t in tags if message.startswith(t)), None)
        if tag is None:
            continue
        text = message[len(tag):]
        if tag == "[degoog] ":
            text = f"degoog: {text}"
        rows.append({
            "time": time,
            "text": text,
            "warn": "1" if level in ("WARNING", "ERROR", "CRITICAL") else "",
        })
    return rows[-_LOG_TAIL_LINES:]


def _speaker(role: str, agent: str) -> dict:
    """Who said a turn, as the console colours it: you, HOPE, Atlas, or one of
    the spawned researchers (any other agent name; they're named after their
    voice, e.g. "sarah")."""
    if role == "user":
        return {"is_user": True, "kind": "user", "speaker": "You"}
    agent = (agent or "hope").strip().lower()
    if agent == "hope":
        return {"is_user": False, "kind": "hope", "speaker": "HOPE"}
    if agent == "atlas":
        return {"is_user": False, "kind": "atlas", "speaker": "Atlas"}
    return {"is_user": False, "kind": "subagent", "speaker": agent.capitalize()}


def _headline(summary: str) -> str:
    """First sentence of the session summary, used as the thread's name.

    Sessions have no titles; the summary is the only human-written description
    of what happened, and its opening sentence is reliably the topic.
    """
    if not summary or summary.startswith(_UNSUMMARIZED):
        return "Not summarized yet"
    first = summary.strip().split(". ")[0].strip().rstrip(".")
    return first if len(first) <= 70 else first[:67].rstrip() + "…"


class DashboardState(rx.State):
    # ── chrome ──────────────────────────────────────────────────
    sidebar_collapsed: bool = False
    console_open: bool = True
    console_x: int = 800
    console_y: int = 40

    # Which conversation the console is showing. LIVE_THREAD_ID means "now".
    selected_thread: str = LIVE_THREAD_ID

    # ── live feed ───────────────────────────────────────────────
    live_state: str = "idle"
    live_agent: str = ""
    live_context_pct: float = 0.0
    live_session_id: str = ""
    live_turns: list[dict] = []

    # ── history ─────────────────────────────────────────────────
    sessions: list[dict] = []
    transcript: list[dict] = []
    transcript_loading: bool = False

    # ── corkboard ───────────────────────────────────────────────
    notes: list[dict] = NOTE_LAYOUT
    new_task_drafts: dict[str, str] = {"n3": "", "n4": "", "n5": ""}

    # ── log cards ───────────────────────────────────────────────
    # Three views of hope.log: everything, tool calls, web activity. Keyed so
    # they share one set of open/close and drag handlers.
    log_open: dict[str, bool] = {"log": True, "tools": True, "web": True}
    log_x: dict[str, int] = {"log": 300, "tools": 1390, "web": 1390}
    log_y: dict[str, int] = {"log": 670, "tools": 40, "web": 364}
    terminal_lines: list[str] = []
    tool_rows: list[dict[str, str]] = []
    web_rows: list[dict[str, str]] = []

    # ── drag tracking (one thing at a time) ─────────────────────
    dragging_note_id: str = ""
    _note_drag_start: tuple[int, int] = (0, 0)
    _note_drag_orig: tuple[int, int] = (0, 0)
    dragging_console: bool = False
    _console_drag_start: tuple[int, int] = (0, 0)
    _console_drag_orig: tuple[int, int] = (0, 0)
    dragging_log: str = ""
    _log_drag_start: tuple[int, int] = (0, 0)
    _log_drag_orig: tuple[int, int] = (0, 0)

    # ── computed ────────────────────────────────────────────────

    @rx.var
    def is_dragging(self) -> bool:
        """Text selection fights a pointer drag: without this, dragging a note
        paints a selection across the whole board. Scoped to the drag so text
        stays selectable the rest of the time."""
        return bool(self.dragging_note_id) or self.dragging_console or bool(self.dragging_log)

    @rx.var
    def is_live_selected(self) -> bool:
        return self.selected_thread == LIVE_THREAD_ID

    @rx.var
    def hope_is_running(self) -> bool:
        return self.live_state != "idle"

    @rx.var
    def live_status_label(self) -> str:
        """Plain words, not jargon. 'idle' is the one that needs explaining:
        it means the process isn't up, which is not obvious from the word."""
        return {
            "listening": "Listening",
            "thinking": "Thinking",
            "speaking": "Speaking",
        }.get(self.live_state, "Not running")

    @rx.var
    def context_label(self) -> str:
        return f"{self.live_context_pct:.0%} context used"

    @rx.var
    def thread_rows(self) -> list[dict]:
        return [
            {
                **session,
                "active": session["id"] == self.selected_thread,
            }
            for session in self.sessions
        ]

    @rx.var
    def console_title(self) -> str:
        if self.is_live_selected:
            return "Now"
        for session in self.sessions:
            if session["id"] == self.selected_thread:
                return session["when"]
        return "Conversation"

    @rx.var
    def console_messages(self) -> list[dict]:
        """One shape for both modes, so the message list renders from a single
        component whether it is showing live turns or a stored transcript."""
        if self.is_live_selected:
            return [
                {"key": f"live-{turn['seq']}", **_speaker(turn["role"], turn["agent"]),
                 "text": turn["text"]}
                for turn in self.live_turns
            ]
        return [
            {"key": f"past-{i}", **_speaker(message["role"], message["agent"]),
             "text": message["text"]}
            for i, message in enumerate(self.transcript)
        ]

    @rx.var
    def console_is_empty(self) -> bool:
        return len(self.console_messages) == 0

    @rx.var
    def empty_message(self) -> str:
        """Empty states say what to do, not just that there is nothing here."""
        if not self.is_live_selected:
            return "This conversation has no recorded turns."
        if self.hope_is_running:
            return "HOPE is listening. Start talking and the conversation appears here."
        return "HOPE is not running. Start it with hope.py to talk."

    # ── chrome events ───────────────────────────────────────────

    @rx.event
    def toggle_sidebar(self):
        self.sidebar_collapsed = not self.sidebar_collapsed

    @rx.event
    def close_console(self):
        self.console_open = False

    @rx.event
    def open_console(self):
        self.console_open = True

    # ── thread selection ────────────────────────────────────────

    @rx.event
    async def select_live(self):
        self.selected_thread = LIVE_THREAD_ID
        self.console_open = True
        await self.load_live()

    @rx.event
    async def select_thread(self, session_id: str):
        self.selected_thread = session_id
        self.console_open = True
        self.transcript_loading = True
        yield
        await self.load_transcript(session_id)
        self.transcript_loading = False

    @rx.event
    async def load_transcript(self, session_id: str):
        messages = await asyncio.to_thread(_episodic.get_session_transcript, session_id)
        agent = next(
            (s["agent"] for s in self.sessions if s["id"] == session_id), "hope"
        )
        self.transcript = [
            {"role": m.role, "text": m.content_text or "", "agent": agent}
            for m in messages
            if m.role in _VISIBLE_ROLES and (m.content_text or "").strip()
        ]

    # ── data loading ────────────────────────────────────────────

    @rx.event
    async def load_sessions(self):
        sessions = await asyncio.to_thread(_episodic.list_sessions)
        # The run currently in progress is shown as Live, not as history; it
        # would otherwise appear twice and read as a duplicate.
        current = self.live_session_id
        self.sessions = [
            {
                "id": s.session_id,
                "agent": s.agent,
                "headline": _headline(s.summary),
                "when": _day_label(s.ended_at),
                "ago": _relative_time(s.ended_at),
                "count": s.message_count,
                "count_label": f"{s.message_count} messages",
            }
            for s in sessions
            if s.session_id != current
        ]

    @rx.event
    async def load_live(self):
        status = await asyncio.to_thread(_live.get_status)
        # A row that stopped being touched means the process behind it died
        # without running end_session(). Believing state alone would leave a
        # green "live" indicator up for a HOPE that is not running.
        self.live_state = (
            "idle" if _is_stale(status.updated_at) else status.state
        )
        self.live_agent = status.agent
        self.live_context_pct = status.context_pct
        self.live_session_id = status.session_id
        if status.session_id:
            turns = await asyncio.to_thread(_live.get_turns, status.session_id, 60)
            self.live_turns = [
                {"seq": t.seq, "role": t.role, "agent": t.agent, "text": t.text}
                for t in turns
            ]
        else:
            self.live_turns = []

    @rx.event
    async def load_board(self):
        """Fetch board state and merge it into `self.notes`, leaving each
        note's layout (x/y/rotate/paper/tape/pin/title) untouched so a dragged
        position survives a refresh."""
        today = await asyncio.to_thread(_board.list_items, "today")
        planned = await asyncio.to_thread(_board.list_items, "planned")
        pending = await asyncio.to_thread(_board.list_items, "pending")
        quick_note = await asyncio.to_thread(_board.get_quick_note)
        location = await board_live.get_location_and_time()
        try:
            weather = await board_live.get_weather()
        except Exception:
            weather = None

        tasks_by_list = {"today": today, "planned": planned, "pending": pending}

        def merge(n: dict) -> dict:
            if n["type"] == "location":
                lat, lon = location["lat"], location["lon"]
                ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
                return {
                    **n,
                    "location_city": location["city"],
                    "location_detail": f"{abs(lat):.2f}{ns}, {abs(lon):.2f}{ew}",
                    "location_time": f"{location['local_time']} · {location['local_date']}",
                }
            if n["type"] == "weather":
                if weather is None:
                    return n
                return {
                    **n,
                    "temp": f"{weather['temp_c']}°C",
                    "condition": weather["condition"],
                    "hi": f"{weather['hi_c']}°",
                    "lo": f"{weather['lo_c']}°",
                    "wind": f"{weather['wind_kmh']} km/h",
                }
            if n["type"] == "tasks":
                return {
                    **n,
                    "tasks": [
                        {"id": i.id, "text": i.text, "done": i.done, "agent": i.agent}
                        for i in tasks_by_list[n["list_type"]]
                    ],
                }
            if n["type"] == "notes":
                return {**n, "content": quick_note.content, "note_agent": quick_note.agent}
            return n

        self.notes = [merge(n) for n in self.notes]

    @rx.event
    async def load_terminal(self):
        path = Path(settings.hope_log_path)
        if not path.exists():
            self.terminal_lines = ["No log yet. Start hope.py to see activity here."]
            return
        lines = (await asyncio.to_thread(path.read_text)).splitlines()
        self.terminal_lines = lines[-_LOG_TAIL_LINES:]
        self.tool_rows = _activity_rows(lines, _TOOL_TAGS)
        self.web_rows = _activity_rows(lines, _WEB_TAGS)

    @rx.event
    async def on_page_load(self):
        await self.load_live()
        await self.load_sessions()
        await self.load_board()
        await self.load_terminal()
        return [
            DashboardState.live_refresh_loop,
            DashboardState.board_refresh_loop,
            DashboardState.log_refresh_loop,
            DashboardState.session_refresh_loop,
        ]

    @rx.event(background=True)
    async def live_refresh_loop(self):
        while True:
            await asyncio.sleep(_LIVE_REFRESH_SECONDS)
            async with self:
                await self.load_live()

    @rx.event(background=True)
    async def board_refresh_loop(self):
        while True:
            await asyncio.sleep(_BOARD_REFRESH_SECONDS)
            async with self:
                await self.load_board()

    @rx.event(background=True)
    async def log_refresh_loop(self):
        while True:
            await asyncio.sleep(_LOG_REFRESH_SECONDS)
            async with self:
                await self.load_terminal()

    @rx.event(background=True)
    async def session_refresh_loop(self):
        """Slower than the rest: a new thread only appears when a run ends."""
        while True:
            await asyncio.sleep(_SESSION_REFRESH_SECONDS)
            async with self:
                await self.load_sessions()

    # ── board editing ───────────────────────────────────────────

    @rx.event
    async def toggle_task(self, item_id: int):
        await asyncio.to_thread(_board.toggle_item, item_id, settings.user_name)
        await self.load_board()

    @rx.event
    async def update_task_text(self, item_id: int, value: str):
        await asyncio.to_thread(_board.update_item_text, item_id, value, settings.user_name)
        await self.load_board()

    @rx.event
    def set_new_task_draft(self, note_id: str, value: str):
        self.new_task_drafts = {**self.new_task_drafts, note_id: value}

    @rx.event
    def on_new_task_key_down(self, note_id: str, list_type: str, key: str, info: dict):
        if key == "Enter" and not info.get("shift_key"):
            return DashboardState.add_task_ui(note_id, list_type)

    @rx.event
    async def add_task_ui(self, note_id: str, list_type: str):
        text = self.new_task_drafts.get(note_id, "").strip()
        if not text:
            return
        await asyncio.to_thread(_board.add_item, list_type, text, settings.user_name)
        self.new_task_drafts = {**self.new_task_drafts, note_id: ""}
        await self.load_board()

    @rx.event
    async def edit_note_content(self, value: str):
        await asyncio.to_thread(_board.update_quick_note, value, settings.user_name)
        await self.load_board()

    # ── log cards ───────────────────────────────────────────────

    @rx.event
    def close_log(self, card: str):
        self.log_open = {**self.log_open, card: False}

    @rx.event
    def open_log(self, card: str):
        self.log_open = {**self.log_open, card: True}

    # ── dragging ────────────────────────────────────────────────

    @rx.event
    def start_note_drag(self, note_id: str, info: dict):
        note = next(n for n in self.notes if n["id"] == note_id)
        self.dragging_note_id = note_id
        self._note_drag_start = (info["client_x"], info["client_y"])
        self._note_drag_orig = (note["x"], note["y"])

    @rx.event
    def start_console_drag(self, info: dict):
        self.dragging_console = True
        self._console_drag_start = (info["client_x"], info["client_y"])
        self._console_drag_orig = (self.console_x, self.console_y)

    @rx.event
    def start_log_drag(self, card: str, info: dict):
        self.dragging_log = card
        self._log_drag_start = (info["client_x"], info["client_y"])
        self._log_drag_orig = (self.log_x[card], self.log_y[card])

    @rx.event(throttle=16)
    def on_root_mouse_move(self, info: dict):
        if self.dragging_note_id:
            sx, sy = self._note_drag_start
            ox, oy = self._note_drag_orig
            nx, ny = ox + (info["client_x"] - sx), oy + (info["client_y"] - sy)
            note_id = self.dragging_note_id
            self.notes = [
                {**n, "x": nx, "y": ny} if n["id"] == note_id else n for n in self.notes
            ]
        elif self.dragging_console:
            sx, sy = self._console_drag_start
            ox, oy = self._console_drag_orig
            self.console_x = ox + (info["client_x"] - sx)
            self.console_y = oy + (info["client_y"] - sy)
        elif self.dragging_log:
            sx, sy = self._log_drag_start
            ox, oy = self._log_drag_orig
            card = self.dragging_log
            self.log_x = {**self.log_x, card: ox + (info["client_x"] - sx)}
            self.log_y = {**self.log_y, card: oy + (info["client_y"] - sy)}

    @rx.event
    def on_root_mouse_up(self, info: dict):
        self.dragging_note_id = ""
        self.dragging_console = False
        self.dragging_log = ""

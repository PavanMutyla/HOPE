"""Dashboard state. The chat panel is still Phase 1 (mock data, no backend),
ported from the Component class in the Claude Design prototype's `HOPE
Dashboard.dc.html`. The corkboard notes are real: Today/Planned/Pending/Quick
notes and Location/Weather are backed by the shared board (memory/board/) —
the same tools HOPE and Atlas call by voice.
"""

import dashboard._pathfix  # noqa: F401 — sys.path side effect, must run first

import asyncio
import time
from pathlib import Path

import reflex as rx

from dashboard.data import AGENT_META, INITIAL_CHATS, MOCK_ATTACHMENT_NAMES, NOTE_LAYOUT
from memory.board import live as board_live
from memory.board.store import Board
from settings import settings

REGENERATE_TEXT = "Here's another take on that — regenerated response for the prototype."
MOCK_REPLY_TEXT = "Noted — I'll factor that in. (This is a mocked response for the prototype.)"

_board = Board()
_REFRESH_SECONDS = 15
_LOG_REFRESH_SECONDS = 3
_LOG_TAIL_LINES = 200


class DashboardState(rx.State):
    # Sidebar
    sidebar_collapsed: bool = False

    # Chat panel chrome — positioned clear of the corkboard notes (which
    # occupy roughly screen-x 300-780 with the sidebar expanded), not on
    # top of them.
    panel_open: bool = True
    panel_x: int = 820
    panel_y: int = 40
    model: str = "HOPE"
    model_menu_open: bool = False
    attach_menu_open: bool = False
    listening: bool = False

    # Chats + active thread
    chats: list[dict] = INITIAL_CHATS
    active_chat_id: str = "c1"

    # Composer
    compose_text: str = ""
    attachments: list[dict] = []
    is_thinking: bool = False

    # Message editing
    editing_msg_id: str = ""
    edit_drafts: dict[str, str] = {}

    # Corkboard notes — layout (position/paper/etc.) is static; content is
    # merged in live from the shared board by load_board().
    notes: list[dict] = NOTE_LAYOUT

    # Drag tracking (panel XOR one note at a time, matching the prototype)
    dragging_note_id: str = ""
    _note_drag_start: tuple[int, int] = (0, 0)
    _note_drag_orig: tuple[int, int] = (0, 0)
    dragging_panel: bool = False
    _panel_drag_start: tuple[int, int] = (0, 0)
    _panel_drag_orig: tuple[int, int] = (0, 0)

    # Terminal (HOPE log tail) panel — under the notes column, clear of both
    # the notes and the chat panel (which sits to the right, see panel_x).
    terminal_open: bool = True
    terminal_x: int = 300
    terminal_y: int = 670
    terminal_lines: list[str] = []
    dragging_terminal: bool = False
    _terminal_drag_start: tuple[int, int] = (0, 0)
    _terminal_drag_orig: tuple[int, int] = (0, 0)

    # ---- computed ----

    @rx.var
    def active_chat(self) -> dict:
        for chat in self.chats:
            if chat["id"] == self.active_chat_id:
                return chat
        return self.chats[0] if self.chats else {"id": "", "messages": []}

    @rx.var
    def display_messages(self) -> list[dict]:
        out = []
        for m in self.active_chat["messages"]:
            if m["role"] == "user":
                is_editing = self.editing_msg_id == m["id"]
                out.append({
                    **m,
                    "is_user": True,
                    "is_editing": is_editing,
                    "edit_value": self.edit_drafts.get(m["id"], m["text"]),
                })
                continue
            versions = m.get("versions") or [m.get("text", "")]
            av = m.get("active_version", 0)
            meta = AGENT_META.get(m.get("agent", "HOPE"), AGENT_META["HOPE"])
            out.append({
                **m,
                "is_user": False,
                "avatar_color": meta["color"],
                "avatar_initial": meta["initial"],
                "agent_name": m.get("agent", "HOPE"),
                "text": versions[av],
                "has_versions": len(versions) > 1,
                "version_label": f"{av + 1}/{len(versions)}",
            })
        return out

    @rx.var
    def chat_list(self) -> list[dict]:
        out = []
        for c in self.chats:
            first = c["messages"][0]["text"] if c["messages"] else "no messages yet"
            out.append({
                "id": c["id"],
                "title": c["title"],
                "time": c["time"],
                "dot": c["dot"],
                "initial": c["title"][:1].upper(),
                "preview": first[:30],
                "active": c["id"] == self.active_chat_id,
            })
        return out

    # ---- sidebar / chrome ----

    @rx.event
    def toggle_sidebar(self):
        self.sidebar_collapsed = not self.sidebar_collapsed

    @rx.event
    def toggle_model_menu(self):
        self.model_menu_open = not self.model_menu_open

    @rx.event
    def select_model(self, name: str):
        self.model = name
        self.model_menu_open = False

    @rx.event
    def toggle_attach_menu(self):
        self.attach_menu_open = not self.attach_menu_open

    @rx.event
    def toggle_voice(self):
        self.listening = not self.listening

    @rx.event
    def close_panel(self):
        self.panel_open = False

    # ---- chats ----

    def _update_chat(self, chat_id: str, fn):
        self.chats = [fn(c) if c["id"] == chat_id else c for c in self.chats]

    @rx.event
    def new_chat(self):
        new_id = f"c{int(time.time() * 1000)}"
        chat = {
            "id": new_id, "title": "New conversation", "time": "now",
            "dot": "oklch(0.78 0.14 200)", "messages": [],
        }
        self.chats = [chat, *self.chats]
        self.active_chat_id = new_id
        self.panel_open = True

    @rx.event
    def select_chat(self, chat_id: str):
        self.active_chat_id = chat_id
        self.panel_open = True

    # ---- composer ----

    @rx.event
    def set_compose_text(self, value: str):
        self.compose_text = value

    @rx.event
    def on_compose_key_down(self, key: str, info: dict):
        if key == "Enter" and not info.get("shift_key"):
            return DashboardState.send_message

    @rx.event
    async def send_message(self):
        text = self.compose_text.strip()
        if not text:
            return
        chat_id = self.active_chat_id
        user_msg = {"id": f"m{int(time.time() * 1000)}", "role": "user", "text": text}
        self._update_chat(chat_id, lambda c: {**c, "messages": [*c["messages"], user_msg]})
        self.compose_text = ""
        self.is_thinking = True
        self.attachments = []
        yield
        await asyncio.sleep(0.7)
        reply = {
            "id": f"m{int(time.time() * 1000) + 1}", "role": "assistant",
            "agent": self.model, "active_version": 0, "versions": [MOCK_REPLY_TEXT],
        }
        self._update_chat(chat_id, lambda c: {**c, "messages": [*c["messages"], reply]})
        self.is_thinking = False

    # ---- shared board (real, DB-backed) ----

    @rx.event
    async def load_board(self):
        """Fetch current board state and merge it into `self.notes`, leaving
        each note's layout (x/y/rotate/paper/tape/pin/title) untouched — only
        overwrites the content fields, so a dragged position survives a
        refresh."""
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
                items = tasks_by_list[n["list_type"]]
                return {
                    **n,
                    "tasks": [
                        {"id": i.id, "text": i.text, "done": i.done, "agent": i.agent}
                        for i in items
                    ],
                }
            if n["type"] == "notes":
                return {**n, "content": quick_note.content, "note_agent": quick_note.agent}
            return n

        self.notes = [merge(n) for n in self.notes]

    @rx.event
    async def on_page_load(self):
        await self.load_board()
        await self.load_terminal()
        return [DashboardState.refresh_loop, DashboardState.log_refresh_loop]

    @rx.event(background=True)
    async def refresh_loop(self):
        while True:
            await asyncio.sleep(_REFRESH_SECONDS)
            async with self:
                await self.load_board()

    # ---- terminal (HOPE log tail) ----

    @rx.event
    async def load_terminal(self):
        path = Path(settings.hope_log_path)
        if not path.exists():
            self.terminal_lines = ["No logs yet — start hope.py to see live activity here."]
            return
        lines = await asyncio.to_thread(path.read_text)
        self.terminal_lines = lines.splitlines()[-_LOG_TAIL_LINES:]

    @rx.event(background=True)
    async def log_refresh_loop(self):
        while True:
            await asyncio.sleep(_LOG_REFRESH_SECONDS)
            async with self:
                await self.load_terminal()

    @rx.event
    def close_terminal(self):
        self.terminal_open = False

    @rx.event
    def start_terminal_drag(self, info: dict):
        self.dragging_terminal = True
        self._terminal_drag_start = (info["client_x"], info["client_y"])
        self._terminal_drag_orig = (self.terminal_x, self.terminal_y)

    @rx.event
    async def toggle_task(self, item_id: int):
        await asyncio.to_thread(_board.toggle_item, item_id, settings.user_name)
        await self.load_board()

    @rx.event
    async def edit_note_content(self, value: str):
        await asyncio.to_thread(_board.update_quick_note, value, settings.user_name)
        await self.load_board()

    # ---- message actions ----

    @rx.event
    def regenerate(self, chat_id: str, msg_id: str):
        def add_version(c):
            messages = []
            for m in c["messages"]:
                if m["id"] == msg_id:
                    versions = [*m["versions"], REGENERATE_TEXT]
                    m = {**m, "versions": versions, "active_version": len(versions) - 1}
                messages.append(m)
            return {**c, "messages": messages}

        self._update_chat(chat_id, add_version)

    @rx.event
    def switch_version(self, chat_id: str, msg_id: str, direction: int):
        def shift(c):
            messages = []
            for m in c["messages"]:
                if m["id"] == msg_id:
                    n = len(m["versions"])
                    new_av = max(0, min(n - 1, m["active_version"] + direction))
                    m = {**m, "active_version": new_av}
                messages.append(m)
            return {**c, "messages": messages}

        self._update_chat(chat_id, shift)

    @rx.event
    def start_edit(self, msg_id: str, text: str):
        self.editing_msg_id = msg_id
        self.edit_drafts = {**self.edit_drafts, msg_id: text}

    @rx.event
    def edit_change(self, msg_id: str, value: str):
        self.edit_drafts = {**self.edit_drafts, msg_id: value}

    @rx.event
    def cancel_edit(self):
        self.editing_msg_id = ""

    @rx.event
    def save_edit(self, chat_id: str, msg_id: str):
        draft = self.edit_drafts.get(msg_id, "")

        def apply(c):
            return {
                **c,
                "messages": [
                    {**m, "text": draft} if m["id"] == msg_id else m
                    for m in c["messages"]
                ],
            }

        self._update_chat(chat_id, apply)
        self.editing_msg_id = ""

    @rx.event
    def copy_text(self, text: str):
        return rx.set_clipboard(text)

    # ---- attachments ----

    @rx.event
    def add_attachment(self, type_: str):
        self.attachments = [
            *self.attachments,
            {"id": f"a{int(time.time() * 1000)}", "type": type_, "name": MOCK_ATTACHMENT_NAMES[type_]},
        ]
        self.attach_menu_open = False

    @rx.event
    def remove_attachment(self, att_id: str):
        self.attachments = [a for a in self.attachments if a["id"] != att_id]

    # ---- note drag ----

    @rx.event
    def start_note_drag(self, note_id: str, info: dict):
        note = next(n for n in self.notes if n["id"] == note_id)
        self.dragging_note_id = note_id
        self._note_drag_start = (info["client_x"], info["client_y"])
        self._note_drag_orig = (note["x"], note["y"])

    @rx.event
    def start_panel_drag(self, info: dict):
        self.dragging_panel = True
        self._panel_drag_start = (info["client_x"], info["client_y"])
        self._panel_drag_orig = (self.panel_x, self.panel_y)

    @rx.event(throttle=16)
    def on_root_mouse_move(self, info: dict):
        if self.dragging_note_id:
            sx, sy = self._note_drag_start
            ox, oy = self._note_drag_orig
            nx = ox + (info["client_x"] - sx)
            ny = oy + (info["client_y"] - sy)
            note_id = self.dragging_note_id
            self.notes = [
                {**n, "x": nx, "y": ny} if n["id"] == note_id else n for n in self.notes
            ]
        elif self.dragging_panel:
            sx, sy = self._panel_drag_start
            ox, oy = self._panel_drag_orig
            self.panel_x = ox + (info["client_x"] - sx)
            self.panel_y = oy + (info["client_y"] - sy)
        elif self.dragging_terminal:
            sx, sy = self._terminal_drag_start
            ox, oy = self._terminal_drag_orig
            self.terminal_x = ox + (info["client_x"] - sx)
            self.terminal_y = oy + (info["client_y"] - sy)

    @rx.event
    def on_root_mouse_up(self, info: dict):
        self.dragging_note_id = ""
        self.dragging_panel = False
        self.dragging_terminal = False

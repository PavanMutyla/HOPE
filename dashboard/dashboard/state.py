"""Dashboard state — Phase 1 (mock data, no backend). Ported from the
Component class in the Claude Design prototype's `HOPE Dashboard.dc.html`;
event handler names and behavior match 1:1 where the prototype's React
setState pattern translates directly to Reflex state mutation.
"""

import asyncio
import time

import reflex as rx

from dashboard.data import AGENT_META, INITIAL_CHATS, INITIAL_NOTES, MOCK_ATTACHMENT_NAMES

REGENERATE_TEXT = "Here's another take on that — regenerated response for the prototype."
MOCK_REPLY_TEXT = "Noted — I'll factor that in. (This is a mocked response for the prototype.)"


class DashboardState(rx.State):
    # Sidebar
    sidebar_collapsed: bool = False

    # Chat panel chrome
    panel_open: bool = True
    panel_x: int = 560
    panel_y: int = 50
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

    # Corkboard notes
    notes: list[dict] = INITIAL_NOTES

    # Drag tracking (panel XOR one note at a time, matching the prototype)
    dragging_note_id: str = ""
    _note_drag_start: tuple[int, int] = (0, 0)
    _note_drag_orig: tuple[int, int] = (0, 0)
    dragging_panel: bool = False
    _panel_drag_start: tuple[int, int] = (0, 0)
    _panel_drag_orig: tuple[int, int] = (0, 0)

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

    @rx.event
    def toggle_task(self, note_id: str, idx: int):
        def flip(n):
            if n["id"] != note_id:
                return n
            tasks = list(n["tasks"])
            tasks[idx] = {**tasks[idx], "done": not tasks[idx]["done"]}
            return {**n, "tasks": tasks}

        self.notes = [flip(n) for n in self.notes]

    @rx.event
    def edit_note_content(self, note_id: str, value: str):
        self.notes = [
            {**n, "content": value} if n["id"] == note_id else n for n in self.notes
        ]

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

    @rx.event
    def on_root_mouse_up(self, info: dict):
        self.dragging_note_id = ""
        self.dragging_panel = False

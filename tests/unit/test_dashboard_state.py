"""Unit tests for the Reflex dashboard's DashboardState.

Until now `dashboard/dashboard/state.py` — 460-odd lines holding every piece of
dashboard behaviour — had no test at all, while the board layer underneath it
(tests/unit/test_board_store.py, tests/integration/test_board_tools.py) was well
covered. This file covers the layer in between: the merge that folds live board
data into the note layout, the drag arithmetic, and the chat-panel view models.

Two things worth knowing before adding to this file:

- Reflex refuses direct instantiation of a State outside a running app, except
  under pytest (`reflex.utils.exec.is_testing_env()` checks PYTEST_CURRENT_TEST,
  which pytest sets per-test). So `DashboardState()` only works inside a test
  body — never at module import time or in a session-scoped fixture built during
  collection.
- `state.py` builds a module-level `_board = Board()` at import. conftest's
  pytest_configure points BOARD_DB_PATH at a temp dir so that import can't touch
  the real board, and `board` below swaps in a per-test Board on top of that.
"""

import pytest

from dashboard.data import AGENT_META, NOTE_LAYOUT
from dashboard.state import MOCK_REPLY_TEXT, REGENERATE_TEXT, DashboardState
from dashboard import state as state_module
from memory.board.store import Board

pytestmark = pytest.mark.unit


@pytest.fixture
def board(tmp_path, monkeypatch):
    """Per-test Board, swapped in for the module-level singleton that every
    event handler reaches for by global name."""
    b = Board(db_path=tmp_path / "board.db")
    monkeypatch.setattr(state_module, "_board", b)
    yield b
    b.close()


@pytest.fixture
def offline_live(monkeypatch):
    """load_board() calls out to IP geolocation and Open-Meteo. Stub both so
    these tests stay offline and deterministic."""
    async def fake_location():
        return {
            "city": "Bengaluru", "lat": 12.97, "lon": 77.59,
            "local_time": "4:20 PM", "local_date": "Tuesday, September 2",
        }

    async def fake_weather():
        return {
            "temp_c": 27, "condition": "Partly cloudy",
            "hi_c": 30, "lo_c": 21, "wind_kmh": 11,
        }

    monkeypatch.setattr(state_module.board_live, "get_location_and_time", fake_location)
    monkeypatch.setattr(state_module.board_live, "get_weather", fake_weather)


def note(state: DashboardState, note_id: str) -> dict:
    return next(n for n in state.notes if n["id"] == note_id)


# ─── computed vars ──────────────────────────────────────────────

def test_active_chat_follows_active_chat_id():
    s = DashboardState()
    s.active_chat_id = "c2"
    assert s.active_chat["title"] == "Debug useEffect loop"


def test_active_chat_falls_back_to_first_when_id_is_unknown():
    """A stale id (deleted thread, hand-edited state) must not crash the panel."""
    s = DashboardState()
    s.active_chat_id = "does-not-exist"
    assert s.active_chat["id"] == "c1"


def test_active_chat_is_safe_when_there_are_no_chats_at_all():
    s = DashboardState()
    s.chats = []
    assert s.active_chat == {"id": "", "messages": []}


def test_display_messages_marks_user_turns_and_carries_the_edit_draft():
    s = DashboardState()
    s.editing_msg_id = "m1"
    s.edit_drafts = {"m1": "half-typed edit"}

    first = s.display_messages[0]
    assert first["is_user"] is True
    assert first["is_editing"] is True
    assert first["edit_value"] == "half-typed edit"


def test_display_messages_defaults_the_edit_draft_to_the_message_text():
    s = DashboardState()
    first = s.display_messages[0]
    assert first["is_editing"] is False
    assert first["edit_value"] == first["text"]


def test_display_messages_resolves_assistant_avatar_from_agent_meta():
    s = DashboardState()
    reply = s.display_messages[1]  # m2, agent "Scout"
    assert reply["is_user"] is False
    assert reply["agent_name"] == "Scout"
    assert reply["avatar_color"] == AGENT_META["Scout"]["color"]
    assert reply["avatar_initial"] == "S"


def test_display_messages_falls_back_to_hope_meta_for_an_unknown_agent():
    """Agents are added to the registry over time; one the dashboard hasn't
    heard of must render, not KeyError."""
    s = DashboardState()
    s.chats = [{
        "id": "c1", "title": "t", "time": "now", "dot": "#fff",
        "messages": [{
            "id": "m1", "role": "assistant", "agent": "Atlas",
            "active_version": 0, "versions": ["from an unregistered agent"],
        }],
    }]
    reply = s.display_messages[0]
    assert reply["agent_name"] == "Atlas"
    assert reply["avatar_color"] == AGENT_META["HOPE"]["color"]


def test_display_messages_renders_the_selected_version():
    s = DashboardState()
    s.chats = [{
        "id": "c1", "title": "t", "time": "now", "dot": "#fff",
        "messages": [{
            "id": "m1", "role": "assistant", "agent": "HOPE",
            "active_version": 1, "versions": ["first take", "second take"],
        }],
    }]
    reply = s.display_messages[0]
    assert reply["text"] == "second take"
    assert reply["has_versions"] is True
    assert reply["version_label"] == "2/2"


def test_display_messages_hides_version_nav_for_a_single_version():
    s = DashboardState()
    reply = s.display_messages[3]  # m4, one version
    assert reply["has_versions"] is False
    assert reply["version_label"] == "1/1"


def test_chat_list_truncates_the_preview_to_thirty_characters():
    s = DashboardState()
    row = s.chat_list[0]
    assert row["preview"] == "Can you help me plan a 3 day t"
    assert len(row["preview"]) == 30


def test_chat_list_marks_only_the_active_thread():
    s = DashboardState()
    s.active_chat_id = "c3"
    assert [r["active"] for r in s.chat_list] == [False, False, True, False]


def test_chat_list_handles_an_empty_thread():
    s = DashboardState()
    s.chats = [{"id": "c9", "title": "Fresh", "time": "now", "dot": "#fff", "messages": []}]
    row = s.chat_list[0]
    assert row["preview"] == "no messages yet"
    assert row["initial"] == "F"


# ─── board merge ────────────────────────────────────────────────

async def test_load_board_merges_live_content_without_disturbing_layout(board, offline_live):
    """The whole point of merge(): a note Pavan dragged somewhere must stay
    there across the 15-second refresh loop."""
    s = DashboardState()
    s.notes = [{**n, "x": 999, "y": 888} for n in NOTE_LAYOUT]

    await s.load_board()

    assert all(n["x"] == 999 and n["y"] == 888 for n in s.notes)
    assert note(s, "n1")["location_city"] == "Bengaluru"
    assert note(s, "n2")["temp"] == "27°C"


async def test_load_board_formats_the_location_hemisphere(board, offline_live):
    s = DashboardState()
    await s.load_board()
    assert note(s, "n1")["location_detail"] == "12.97N, 77.59E"
    assert note(s, "n1")["location_time"] == "4:20 PM · Tuesday, September 2"


async def test_load_board_formats_southern_and_western_hemispheres(board, monkeypatch):
    async def southwest():
        return {
            "city": "Lima", "lat": -12.05, "lon": -77.04,
            "local_time": "8:00 AM", "local_date": "Tuesday, September 2",
        }

    async def no_weather():
        raise RuntimeError("offline")

    monkeypatch.setattr(state_module.board_live, "get_location_and_time", southwest)
    monkeypatch.setattr(state_module.board_live, "get_weather", no_weather)

    s = DashboardState()
    await s.load_board()
    assert note(s, "n1")["location_detail"] == "12.05S, 77.04W"


async def test_load_board_leaves_the_weather_note_alone_when_the_api_fails(board, monkeypatch):
    """Open-Meteo being down must not blank out the card or take the board with
    it — the stale reading stays on screen."""
    async def fake_location():
        return {
            "city": "Bengaluru", "lat": 12.97, "lon": 77.59,
            "local_time": "4:20 PM", "local_date": "Tuesday, September 2",
        }

    async def boom():
        raise RuntimeError("open-meteo unreachable")

    monkeypatch.setattr(state_module.board_live, "get_location_and_time", fake_location)
    monkeypatch.setattr(state_module.board_live, "get_weather", boom)

    s = DashboardState()
    s.notes = [{**n, "temp": "19°C"} if n["id"] == "n2" else n for n in NOTE_LAYOUT]

    await s.load_board()

    assert note(s, "n2")["temp"] == "19°C"
    assert note(s, "n1")["location_city"] == "Bengaluru"


async def test_load_board_routes_each_list_into_its_own_note(board, offline_live):
    board.add_item("today", "ship the fold test", "hope")
    board.add_item("planned", "wire the chat loop", "pavan")
    board.add_item("pending", "decide on browser voice", "atlas")

    s = DashboardState()
    await s.load_board()

    assert [t["text"] for t in note(s, "n3")["tasks"]] == ["ship the fold test"]
    assert [t["text"] for t in note(s, "n4")["tasks"]] == ["wire the chat loop"]
    assert [t["text"] for t in note(s, "n5")["tasks"]] == ["decide on browser voice"]
    assert note(s, "n5")["tasks"][0]["agent"] == "atlas"


async def test_load_board_reads_the_quick_note(board, offline_live):
    board.update_quick_note("remember to renew the domain", "hope")

    s = DashboardState()
    await s.load_board()

    assert note(s, "n6")["content"] == "remember to renew the domain"
    assert note(s, "n6")["note_agent"] == "hope"


# ─── task editing ───────────────────────────────────────────────

async def test_toggle_task_persists_to_the_board(board, offline_live):
    item = board.add_item("today", "call the vendor", "pavan")
    s = DashboardState()

    await s.toggle_task(item.id)

    assert board.list_items("today")[0].done is True
    assert note(s, "n3")["tasks"][0]["done"] is True


async def test_update_task_text_persists_to_the_board(board, offline_live):
    item = board.add_item("today", "typo hree", "pavan")
    s = DashboardState()

    await s.update_task_text(item.id, "typo here")

    assert board.list_items("today")[0].text == "typo here"


def test_set_new_task_draft_only_touches_the_named_note():
    s = DashboardState()
    s.set_new_task_draft("n4", "a planned thing")
    assert s.new_task_drafts == {"n3": "", "n4": "a planned thing", "n5": ""}


async def test_add_task_ui_writes_the_draft_and_clears_it(board, offline_live):
    s = DashboardState()
    s.set_new_task_draft("n3", "  buy coffee  ")

    await s.add_task_ui("n3", "today")

    assert [i.text for i in board.list_items("today")] == ["buy coffee"]
    assert s.new_task_drafts["n3"] == ""


async def test_add_task_ui_ignores_a_blank_draft(board, offline_live):
    s = DashboardState()
    s.set_new_task_draft("n3", "   ")

    await s.add_task_ui("n3", "today")

    assert board.list_items("today") == []


def test_enter_submits_a_new_task_but_shift_enter_does_not():
    s = DashboardState()
    assert s.on_new_task_key_down("n3", "today", "Enter", {"shift_key": False}) is not None
    assert s.on_new_task_key_down("n3", "today", "Enter", {"shift_key": True}) is None
    assert s.on_new_task_key_down("n3", "today", "a", {"shift_key": False}) is None


async def test_edit_note_content_persists_the_quick_note(board, offline_live):
    s = DashboardState()
    await s.edit_note_content("new shared scratch text")
    assert board.get_quick_note().content == "new shared scratch text"


# ─── dragging ───────────────────────────────────────────────────

def test_dragging_a_note_moves_it_by_the_pointer_delta():
    s = DashboardState()
    origin = note(s, "n3")
    s.start_note_drag("n3", {"client_x": 100, "client_y": 200})
    s.on_root_mouse_move({"client_x": 130, "client_y": 175})

    assert note(s, "n3")["x"] == origin["x"] + 30
    assert note(s, "n3")["y"] == origin["y"] - 25


def test_dragging_a_note_leaves_every_other_note_where_it_was():
    s = DashboardState()
    before = {n["id"]: (n["x"], n["y"]) for n in s.notes if n["id"] != "n3"}
    s.start_note_drag("n3", {"client_x": 0, "client_y": 0})
    s.on_root_mouse_move({"client_x": 50, "client_y": 50})

    after = {n["id"]: (n["x"], n["y"]) for n in s.notes if n["id"] != "n3"}
    assert after == before


def test_dragging_the_panel_moves_the_panel():
    s = DashboardState()
    s.start_panel_drag({"client_x": 10, "client_y": 10})
    s.on_root_mouse_move({"client_x": 40, "client_y": 60})
    assert (s.panel_x, s.panel_y) == (850, 90)


def test_dragging_the_terminal_moves_the_terminal():
    s = DashboardState()
    s.start_terminal_drag({"client_x": 0, "client_y": 0})
    s.on_root_mouse_move({"client_x": -20, "client_y": 15})
    assert (s.terminal_x, s.terminal_y) == (280, 685)


def test_a_note_drag_wins_over_a_simultaneous_panel_drag():
    """The handler is an if/elif chain, so overlapping drags resolve to one
    thing moving — matching the prototype's panel-XOR-note behaviour."""
    s = DashboardState()
    s.start_panel_drag({"client_x": 0, "client_y": 0})
    s.start_note_drag("n1", {"client_x": 0, "client_y": 0})

    s.on_root_mouse_move({"client_x": 25, "client_y": 25})

    assert note(s, "n1")["x"] == 65
    assert (s.panel_x, s.panel_y) == (820, 40)


def test_mouse_move_does_nothing_when_nothing_is_being_dragged():
    s = DashboardState()
    before = [(n["x"], n["y"]) for n in s.notes]
    s.on_root_mouse_move({"client_x": 500, "client_y": 500})
    assert [(n["x"], n["y"]) for n in s.notes] == before
    assert (s.panel_x, s.panel_y) == (820, 40)


def test_mouse_up_releases_every_drag():
    s = DashboardState()
    s.start_note_drag("n1", {"client_x": 0, "client_y": 0})
    s.dragging_panel = True
    s.dragging_terminal = True

    s.on_root_mouse_up({})

    assert s.dragging_note_id == ""
    assert s.dragging_panel is False
    assert s.dragging_terminal is False


# ─── terminal ───────────────────────────────────────────────────

async def test_load_terminal_tails_the_log(tmp_path, monkeypatch):
    log = tmp_path / "hope.log"
    log.write_text("\n".join(f"line {i}" for i in range(500)))
    monkeypatch.setattr(state_module.settings, "hope_log_path", str(log))

    s = DashboardState()
    await s.load_terminal()

    assert len(s.terminal_lines) == 200
    assert s.terminal_lines[-1] == "line 499"


async def test_load_terminal_explains_itself_when_hope_has_never_run(tmp_path, monkeypatch):
    monkeypatch.setattr(state_module.settings, "hope_log_path", str(tmp_path / "nope.log"))

    s = DashboardState()
    await s.load_terminal()

    assert s.terminal_lines == [
        "No logs yet — start hope.py to see live activity here."
    ]


# ─── chat panel (still mock-backed, Phase 1) ────────────────────

def test_new_chat_prepends_and_activates_it():
    s = DashboardState()
    s.panel_open = False
    s.new_chat()

    assert len(s.chats) == 5
    assert s.chats[0]["title"] == "New conversation"
    assert s.active_chat_id == s.chats[0]["id"]
    assert s.panel_open is True


def test_select_chat_reopens_a_closed_panel():
    s = DashboardState()
    s.panel_open = False
    s.select_chat("c2")
    assert s.active_chat_id == "c2"
    assert s.panel_open is True


async def test_send_message_appends_the_turn_and_a_mock_reply():
    """Pins Phase 1's mocked behaviour so replacing it with the real chat loop
    is a visible, deliberate change to this test rather than a silent one."""
    s = DashboardState()
    s.compose_text = "what's on for today?"
    s.attachments = [{"id": "a1", "type": "Image", "name": "photo.jpg"}]

    async for _ in s.send_message():
        pass

    messages = s.active_chat["messages"]
    assert messages[-2] == {"id": messages[-2]["id"], "role": "user",
                            "text": "what's on for today?"}
    assert messages[-1]["versions"] == [MOCK_REPLY_TEXT]
    assert messages[-1]["agent"] == "HOPE"
    assert s.compose_text == ""
    assert s.attachments == []
    assert s.is_thinking is False


async def test_send_message_ignores_whitespace():
    s = DashboardState()
    before = len(s.active_chat["messages"])
    s.compose_text = "   "

    async for _ in s.send_message():
        pass

    assert len(s.active_chat["messages"]) == before


def test_enter_sends_but_shift_enter_does_not():
    s = DashboardState()
    assert s.on_compose_key_down("Enter", {"shift_key": False}) is not None
    assert s.on_compose_key_down("Enter", {"shift_key": True}) is None
    assert s.on_compose_key_down("a", {"shift_key": False}) is None


def test_regenerate_appends_a_version_and_selects_it():
    s = DashboardState()
    s.regenerate("c1", "m4")

    message = next(m for m in s.active_chat["messages"] if m["id"] == "m4")
    assert message["versions"][-1] == REGENERATE_TEXT
    assert message["active_version"] == 1


def test_switch_version_clamps_at_both_ends():
    s = DashboardState()

    s.switch_version("c1", "m2", -1)  # already at 0
    assert next(m for m in s.active_chat["messages"] if m["id"] == "m2")["active_version"] == 0

    s.switch_version("c1", "m2", 1)
    s.switch_version("c1", "m2", 1)  # only 2 versions exist
    assert next(m for m in s.active_chat["messages"] if m["id"] == "m2")["active_version"] == 1


def test_editing_a_message_saves_the_draft():
    s = DashboardState()
    s.start_edit("m1", "original")
    s.edit_change("m1", "edited text")
    s.save_edit("c1", "m1")

    assert next(m for m in s.active_chat["messages"] if m["id"] == "m1")["text"] == "edited text"
    assert s.editing_msg_id == ""


def test_cancelling_an_edit_leaves_the_message_alone():
    s = DashboardState()
    original = s.active_chat["messages"][0]["text"]
    s.start_edit("m1", original)
    s.edit_change("m1", "discard me")
    s.cancel_edit()

    assert s.active_chat["messages"][0]["text"] == original
    assert s.editing_msg_id == ""


def test_attachments_add_and_remove():
    s = DashboardState()
    s.attach_menu_open = True
    s.add_attachment("Document")

    assert len(s.attachments) == 1
    assert s.attachments[0]["name"] == "notes.pdf"
    assert s.attach_menu_open is False

    s.remove_attachment(s.attachments[0]["id"])
    assert s.attachments == []

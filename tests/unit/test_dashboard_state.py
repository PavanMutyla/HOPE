"""Unit tests for the Reflex dashboard's DashboardState.

The dashboard is read-only by design: HOPE takes voice input, so nothing here
writes to a conversation. What it does do is join three stores into one view,
and that joining is what these tests cover: live feed plus episodic history
plus the shared board.

Two constraints worth knowing before adding to this file:

- Reflex refuses direct instantiation of a State outside a running app, except
  under pytest (`reflex.utils.exec.is_testing_env()` checks PYTEST_CURRENT_TEST,
  which pytest sets per-test). So `DashboardState()` only works inside a test
  body, never at import time or in a fixture built during collection.
- `state.py` builds module-level `Board()`, `EpisodicMemory()` and `LiveFeed()`
  at import. conftest's pytest_configure points their paths at a temp dir so
  that import cannot touch real data, and the fixtures below swap in per-test
  stores on top of that.
"""

import pytest

from dashboard import state as state_module
from dashboard.data import NOTE_LAYOUT
from dashboard.state import LIVE_THREAD_ID, DashboardState
from memory.board.store import Board
from memory.live.store import LiveFeed

pytestmark = pytest.mark.unit

chromadb = pytest.importorskip("chromadb")

from memory.episodic_memory.store import EpisodicMemory  # noqa: E402


@pytest.fixture
def board(tmp_path, monkeypatch):
    b = Board(db_path=tmp_path / "board.db")
    monkeypatch.setattr(state_module, "_board", b)
    yield b
    b.close()


@pytest.fixture
def feed(tmp_path, monkeypatch):
    f = LiveFeed(db_path=tmp_path / "live.db")
    monkeypatch.setattr(state_module, "_live", f)
    yield f
    f.close()


@pytest.fixture
def episodic(tmp_path, monkeypatch, fake_embedding_function):
    m = EpisodicMemory(
        db_path=tmp_path / "episodic.db",
        media_dir=tmp_path / "media",
        persist_dir=tmp_path / "chroma",
        embedding_function=fake_embedding_function,
    )
    monkeypatch.setattr(state_module, "_episodic", m)
    yield m
    m.close()


@pytest.fixture
def offline_live(monkeypatch):
    """load_board() calls IP geolocation and Open-Meteo. Stub both so these
    tests stay offline and deterministic."""
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


def write_session(memory, session_id, summary, texts, ts, agent="hope"):
    memory.write(
        agent=agent, session_id=session_id, reason="session_end",
        span_turns=len(texts), summary=summary,
        messages=[
            {"role": "user" if i % 2 == 0 else "assistant", "content": t}
            for i, t in enumerate(texts)
        ],
    )


# ─── pure helpers ───────────────────────────────────────────────

def test_headline_takes_the_first_sentence_of_the_summary():
    assert state_module._headline(
        "Pavan activated team mode. He then asked about his files."
    ) == "Pavan activated team mode"


def test_headline_truncates_a_long_first_sentence():
    headline = state_module._headline("word " * 40)
    assert len(headline) <= 70
    assert headline.endswith("…")


def test_headline_hides_the_unsummarized_marker():
    """The marker is internal bookkeeping from flush(); showing it verbatim
    leaks an implementation detail into the thread list."""
    raw = "[NOT SUMMARIZED YET — raw session tail, pending upgrade at next startup]\nfoo"
    assert state_module._headline(raw) == "Not summarized yet"


def test_relative_time_buckets():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    assert state_module._relative_time((now - timedelta(seconds=10)).isoformat()) == "just now"
    assert state_module._relative_time((now - timedelta(minutes=5)).isoformat()) == "5m"
    assert state_module._relative_time((now - timedelta(hours=3)).isoformat()) == "3h"
    assert state_module._relative_time((now - timedelta(days=2)).isoformat()) == "2d"


def test_relative_time_survives_junk():
    assert state_module._relative_time("") == ""
    assert state_module._relative_time("not-a-timestamp") == ""


# ─── live feed ──────────────────────────────────────────────────

async def test_live_state_reads_as_not_running_when_hope_is_down(feed):
    s = DashboardState()
    await s.load_live()

    assert s.hope_is_running is False
    assert s.live_status_label == "Not running"
    assert s.live_turns == []


async def test_live_state_tracks_a_running_pipeline(feed):
    feed.start_session("run-1", "hope")
    feed.append_turn("run-1", "user", "", "what's on today?")
    feed.append_turn("run-1", "assistant", "hope", "Three things.")
    feed.set_state("speaking")
    feed.set_context_pct(0.34)

    s = DashboardState()
    await s.load_live()

    assert s.hope_is_running is True
    assert s.live_status_label == "Speaking"
    assert s.context_label == "34% context used"
    assert [t["text"] for t in s.live_turns] == ["what's on today?", "Three things."]


async def test_ended_session_reads_as_not_running_but_keeps_its_turns(feed):
    feed.start_session("run-1", "hope")
    feed.append_turn("run-1", "user", "", "last thing I said")
    feed.end_session()

    s = DashboardState()
    await s.load_live()

    assert s.hope_is_running is False
    assert len(s.live_turns) == 1


# ─── history ────────────────────────────────────────────────────

async def test_sessions_become_thread_rows(episodic, feed):
    write_session(episodic, "s1", "Talked about Orion. Then lunch.", ["hi", "hello"], "19:00")

    s = DashboardState()
    await s.load_sessions()

    assert len(s.sessions) == 1
    assert s.sessions[0]["headline"] == "Talked about Orion"
    assert s.sessions[0]["count_label"] == "2 messages"


async def test_the_running_session_is_not_listed_as_history(episodic, feed):
    """It is shown as Live. Listing it as well would render the same
    conversation twice and read as a duplicate."""
    write_session(episodic, "old-run", "An earlier chat.", ["a", "b"], "18:00")
    write_session(episodic, "current-run", "Happening now.", ["c", "d"], "19:00")
    feed.start_session("current-run", "hope")

    s = DashboardState()
    await s.load_live()
    await s.load_sessions()

    assert [row["id"] for row in s.sessions] == ["old-run"]


async def test_selecting_a_thread_loads_its_transcript(episodic, feed):
    write_session(episodic, "s1", "A chat.", ["question one", "answer one"], "19:00")

    s = DashboardState()
    await s.load_sessions()
    await s.load_transcript("s1")

    assert [m["text"] for m in s.transcript] == ["question one", "answer one"]


async def test_transcript_hides_pipeline_scaffolding(episodic, feed):
    """Warm-start injection and the greeting prompt are `developer` messages
    the pipeline sends itself. Rendering them makes it look like Pavan said
    things he never said."""
    episodic.write(
        agent="hope", session_id="s1", reason="session_end", span_turns=4,
        summary="A chat.",
        messages=[
            {"role": "developer", "content": "Summary of your most recent session..."},
            {"role": "developer", "content": "Say a short hello to Pavan."},
            {"role": "assistant", "content": "Hey Pavan."},
            {"role": "user", "content": "hello"},
        ],
    )

    s = DashboardState()
    await s.load_sessions()
    await s.load_transcript("s1")

    assert [m["role"] for m in s.transcript] == ["assistant", "user"]


async def test_transcript_drops_empty_turns(episodic, feed):
    """A tool-call turn has no text; an empty bubble reads as HOPE saying
    nothing."""
    episodic.write(
        agent="hope", session_id="s1", reason="session_end", span_turns=2,
        summary="A chat.",
        messages=[
            {"role": "assistant", "content": ""},
            {"role": "assistant", "content": "Done."},
        ],
    )

    s = DashboardState()
    await s.load_sessions()
    await s.load_transcript("s1")

    assert [m["text"] for m in s.transcript] == ["Done."]


# ─── console view model ─────────────────────────────────────────

def test_console_defaults_to_live():
    s = DashboardState()
    assert s.selected_thread == LIVE_THREAD_ID
    assert s.is_live_selected is True
    assert s.console_title == "Now"


async def test_console_renders_live_turns_when_live_is_selected(feed):
    feed.start_session("run-1", "hope")
    feed.append_turn("run-1", "user", "", "hello")
    feed.append_turn("run-1", "assistant", "hope", "hi there")

    s = DashboardState()
    await s.load_live()

    messages = s.console_messages
    assert [m["speaker"] for m in messages] == ["You", "HOPE"]
    assert [m["is_user"] for m in messages] == [True, False]


async def test_console_renders_the_transcript_when_a_thread_is_selected(episodic, feed):
    write_session(episodic, "s1", "A chat.", ["asked", "answered"], "19:00")

    s = DashboardState()
    await s.load_sessions()
    s.selected_thread = "s1"
    await s.load_transcript("s1")

    assert s.is_live_selected is False
    assert [m["text"] for m in s.console_messages] == ["asked", "answered"]


async def test_selecting_live_returns_to_now(feed):
    s = DashboardState()
    s.selected_thread = "some-old-session"

    await s.select_live()

    assert s.is_live_selected is True
    assert s.console_open is True


def test_empty_state_tells_you_what_to_do_when_hope_is_down():
    s = DashboardState()
    s.live_state = "idle"
    assert s.console_is_empty is True
    assert "hope.py" in s.empty_message


def test_empty_state_invites_you_to_talk_when_hope_is_up():
    s = DashboardState()
    s.live_state = "listening"
    assert "Start talking" in s.empty_message


def test_empty_state_for_a_past_thread_says_so():
    s = DashboardState()
    s.selected_thread = "s1"
    assert s.empty_message == "This conversation has no recorded turns."


def test_there_is_no_way_to_send_a_message():
    """Pins the product decision: input is voice only. If a compose handler
    ever reappears on this state, that decision was reversed by accident."""
    banned = {"send_message", "compose_text", "on_compose_key_down", "attachments"}
    assert banned.isdisjoint(dir(DashboardState))


# ─── board ──────────────────────────────────────────────────────

async def test_load_board_merges_content_without_disturbing_layout(board, offline_live):
    s = DashboardState()
    s.notes = [{**n, "x": 999, "y": 888} for n in NOTE_LAYOUT]

    await s.load_board()

    assert all(n["x"] == 999 and n["y"] == 888 for n in s.notes)
    assert note(s, "n1")["location_city"] == "Bengaluru"
    assert note(s, "n2")["temp"] == "27°C"


async def test_load_board_formats_hemispheres(board, offline_live):
    s = DashboardState()
    await s.load_board()
    assert note(s, "n1")["location_detail"] == "12.97N, 77.59E"


async def test_weather_failure_leaves_the_stale_card_up(board, monkeypatch):
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


async def test_each_list_lands_in_its_own_note(board, offline_live):
    board.add_item("today", "ship the read path", "hope")
    board.add_item("planned", "browser voice", "pavan")
    board.add_item("pending", "procedural detection", "atlas")

    s = DashboardState()
    await s.load_board()

    assert [t["text"] for t in note(s, "n3")["tasks"]] == ["ship the read path"]
    assert [t["text"] for t in note(s, "n4")["tasks"]] == ["browser voice"]
    assert [t["text"] for t in note(s, "n5")["tasks"]] == ["procedural detection"]


async def test_toggle_and_edit_persist_to_the_board(board, offline_live):
    item = board.add_item("today", "typo hree", "pavan")
    s = DashboardState()

    await s.update_task_text(item.id, "typo here")
    await s.toggle_task(item.id)

    stored = board.list_items("today")[0]
    assert (stored.text, stored.done) == ("typo here", True)


async def test_add_task_writes_the_draft_and_clears_it(board, offline_live):
    s = DashboardState()
    s.set_new_task_draft("n3", "  buy coffee  ")

    await s.add_task_ui("n3", "today")

    assert [i.text for i in board.list_items("today")] == ["buy coffee"]
    assert s.new_task_drafts["n3"] == ""


async def test_blank_task_draft_is_ignored(board, offline_live):
    s = DashboardState()
    s.set_new_task_draft("n3", "   ")
    await s.add_task_ui("n3", "today")
    assert board.list_items("today") == []


def test_enter_submits_a_task_but_shift_enter_does_not():
    s = DashboardState()
    assert s.on_new_task_key_down("n3", "today", "Enter", {"shift_key": False}) is not None
    assert s.on_new_task_key_down("n3", "today", "Enter", {"shift_key": True}) is None


async def test_quick_note_persists(board, offline_live):
    s = DashboardState()
    await s.edit_note_content("renew the domain")
    assert board.get_quick_note().content == "renew the domain"


# ─── dragging ───────────────────────────────────────────────────

def test_dragging_a_note_moves_it_by_the_pointer_delta():
    s = DashboardState()
    origin = note(s, "n3")
    s.start_note_drag("n3", {"client_x": 100, "client_y": 200})
    s.on_root_mouse_move({"client_x": 130, "client_y": 175})

    assert note(s, "n3")["x"] == origin["x"] + 30
    assert note(s, "n3")["y"] == origin["y"] - 25


def test_dragging_a_note_leaves_the_others_alone():
    s = DashboardState()
    before = {n["id"]: (n["x"], n["y"]) for n in s.notes if n["id"] != "n3"}
    s.start_note_drag("n3", {"client_x": 0, "client_y": 0})
    s.on_root_mouse_move({"client_x": 50, "client_y": 50})

    assert {n["id"]: (n["x"], n["y"]) for n in s.notes if n["id"] != "n3"} == before


def test_a_note_drag_wins_over_a_simultaneous_console_drag():
    s = DashboardState()
    s.start_console_drag({"client_x": 0, "client_y": 0})
    s.start_note_drag("n1", {"client_x": 0, "client_y": 0})

    s.on_root_mouse_move({"client_x": 25, "client_y": 25})

    assert note(s, "n1")["x"] == 65
    assert (s.console_x, s.console_y) == (800, 40)


def test_mouse_move_does_nothing_when_nothing_is_dragging():
    s = DashboardState()
    before = [(n["x"], n["y"]) for n in s.notes]
    s.on_root_mouse_move({"client_x": 500, "client_y": 500})
    assert [(n["x"], n["y"]) for n in s.notes] == before


def test_mouse_up_releases_every_drag():
    s = DashboardState()
    s.start_note_drag("n1", {"client_x": 0, "client_y": 0})
    s.dragging_console = True
    s.dragging_log = "tools"

    s.on_root_mouse_up({})

    assert s.dragging_note_id == ""
    assert s.dragging_console is False
    assert s.dragging_log == ""


# ─── terminal ───────────────────────────────────────────────────

async def test_terminal_tails_the_log(tmp_path, monkeypatch):
    log = tmp_path / "hope.log"
    log.write_text("\n".join(f"line {i}" for i in range(500)))
    monkeypatch.setattr(state_module.settings, "hope_log_path", str(log))

    s = DashboardState()
    await s.load_terminal()

    assert len(s.terminal_lines) == 200
    assert s.terminal_lines[-1] == "line 499"


async def test_terminal_explains_itself_when_hope_has_never_run(tmp_path, monkeypatch):
    monkeypatch.setattr(state_module.settings, "hope_log_path", str(tmp_path / "nope.log"))

    s = DashboardState()
    await s.load_terminal()

    assert s.terminal_lines == ["No log yet. Start hope.py to see activity here."]


def test_closed_panels_can_be_reopened():
    """Closing was one-way in the prototype: nothing brought a panel back."""
    s = DashboardState()
    s.close_console()
    for card in ("log", "tools", "web"):
        s.close_log(card)
    assert s.console_open is False
    assert s.log_open == {"log": False, "tools": False, "web": False}

    s.open_console()
    for card in ("log", "tools", "web"):
        s.open_log(card)
    assert s.console_open is True
    assert s.log_open == {"log": True, "tools": True, "web": True}


# ─── liveness ───────────────────────────────────────────────────

def test_a_stale_row_is_treated_as_not_running():
    """end_session() only runs on a clean shutdown. A killed hope.py leaves
    state='listening' behind forever, and without this the dashboard shows a
    green live indicator for a process that no longer exists."""
    from datetime import datetime, timedelta, timezone

    old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    assert state_module._is_stale(old) is True


def test_a_freshly_heartbeated_row_is_believed():
    from datetime import datetime, timezone

    assert state_module._is_stale(datetime.now(timezone.utc).isoformat()) is False


def test_an_unwritten_row_is_stale():
    assert state_module._is_stale("") is True
    assert state_module._is_stale("not-a-timestamp") is True


async def test_load_live_reports_not_running_for_a_stale_session(feed, monkeypatch):
    feed.start_session("run-1", "hope")
    feed.append_turn("run-1", "user", "", "said before the crash")
    # simulate the process dying: state stays 'listening', nothing heartbeats
    monkeypatch.setattr(state_module, "_LIVE_STALE_SECONDS", -1)

    s = DashboardState()
    await s.load_live()

    assert s.live_state == "idle"
    assert s.hope_is_running is False
    # the turns are still there to read; only the liveness claim is withdrawn
    assert len(s.live_turns) == 1


def _loguru(time: str, level: str, message: str) -> str:
    return f"2026-10-26 {time}.123 | {level:<8} | some.module:fn:12 - {message}"


async def test_tool_and_web_cards_filter_the_same_log(tmp_path, monkeypatch):
    log = tmp_path / "hope.log"
    log.write_text("\n".join([
        _loguru("23:50:01", "DEBUG", "OpenAILLMService#0: Generating chat"),
        _loguru("23:50:02", "INFO", "[tool] hope → search_web(query='kokoro')"),
        _loguru("23:50:02", "INFO", '[web] hope searching: "kokoro"'),
        _loguru("23:50:03", "INFO", "[tool] search_web answered in 1.2s (300 chars)"),
        _loguru("23:50:04", "INFO", "[agents] Spawned researcher Sarah (af_sarah): voices"),
        _loguru("23:50:05", "WARNING", "[research] Sarah blocked: localhost is private"),
        _loguru("23:50:06", "INFO", "[degoog] Ready on 127.0.0.1:4444"),
        "    a traceback line with [tool] in it",
    ]))
    monkeypatch.setattr(state_module.settings, "hope_log_path", str(log))

    s = DashboardState()
    await s.load_terminal()

    assert len(s.terminal_lines) == 8  # the Log card still shows everything
    assert s.tool_rows == [
        {"time": "23:50:02", "text": "hope → search_web(query='kokoro')", "warn": ""},
        {"time": "23:50:03", "text": "search_web answered in 1.2s (300 chars)", "warn": ""},
    ]
    assert [r["text"] for r in s.web_rows] == [
        'hope searching: "kokoro"',
        "Spawned researcher Sarah (af_sarah): voices",
        "Sarah blocked: localhost is private",
        "degoog: Ready on 127.0.0.1:4444",
    ]
    assert [r["warn"] for r in s.web_rows] == ["", "", "1", ""]


async def test_activity_cards_keep_only_the_latest_rows(tmp_path, monkeypatch):
    log = tmp_path / "hope.log"
    log.write_text("\n".join(
        _loguru("23:50:01", "INFO", f"[tool] hope → get_tasks(n={i})") for i in range(300)
    ))
    monkeypatch.setattr(state_module.settings, "hope_log_path", str(log))

    s = DashboardState()
    await s.load_terminal()

    assert len(s.tool_rows) == 200
    assert s.tool_rows[-1]["text"] == "hope → get_tasks(n=299)"
    assert s.web_rows == []


def test_dragging_a_log_card_moves_only_that_card():
    s = DashboardState()
    start = (dict(s.log_x), dict(s.log_y))
    s.start_log_drag("web", {"client_x": 100, "client_y": 100})
    s.on_root_mouse_move({"client_x": 130, "client_y": 80})

    assert (s.log_x["web"], s.log_y["web"]) == (start[0]["web"] + 30, start[1]["web"] - 20)
    assert s.log_x["log"] == start[0]["log"] and s.log_y["tools"] == start[1]["tools"]


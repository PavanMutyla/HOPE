"""Unit tests for the shared board's SQLite layer — task add/update/toggle/
delete and the quick-notes singleton. See memory/board/migrations/0001_init.sql
for the schema."""

import pytest

from memory.board import board

pytestmark = pytest.mark.unit


@pytest.fixture
def conn(tmp_path):
    connection = board.connect(tmp_path / "board.db")
    yield connection
    connection.close()


def test_add_item_defaults_to_not_done(conn):
    item = board.add_item(conn, "today", "buy milk", "hope")

    assert item.list_type == "today"
    assert item.text == "buy milk"
    assert item.done is False
    assert item.agent == "hope"


def test_get_item_returns_none_for_missing_id(conn):
    assert board.get_item(conn, 999) is None


def test_update_item_text_changes_text_and_agent(conn):
    item = board.add_item(conn, "today", "buy milk", "hope")

    updated = board.update_item_text(conn, item.id, "buy oat milk", "atlas")

    assert updated.text == "buy oat milk"
    assert updated.agent == "atlas"


def test_update_item_text_returns_none_for_missing_id(conn):
    assert board.update_item_text(conn, 999, "x", "hope") is None


def test_toggle_item_flips_done_and_stamps_agent(conn):
    item = board.add_item(conn, "today", "buy milk", "hope")

    toggled = board.toggle_item(conn, item.id, "atlas")
    assert toggled.done is True
    assert toggled.agent == "atlas"

    toggled_back = board.toggle_item(conn, item.id, "hope")
    assert toggled_back.done is False
    assert toggled_back.agent == "hope"


def test_toggle_item_returns_none_for_missing_id(conn):
    assert board.toggle_item(conn, 999, "hope") is None


def test_delete_item_removes_it(conn):
    item = board.add_item(conn, "today", "buy milk", "hope")

    deleted = board.delete_item(conn, item.id)

    assert deleted is True
    assert board.get_item(conn, item.id) is None


def test_delete_item_returns_false_for_missing_id(conn):
    assert board.delete_item(conn, 999) is False


def test_list_items_filters_by_list_type(conn):
    today_item = board.add_item(conn, "today", "today task", "hope")
    board.add_item(conn, "planned", "planned task", "hope")

    today_items = board.list_items(conn, "today")

    assert [i.id for i in today_items] == [today_item.id]


def test_list_items_on_empty_store_returns_empty_list(conn):
    assert board.list_items(conn, "today") == []


def test_get_quick_note_defaults_to_empty(conn):
    note = board.get_quick_note(conn)
    assert note.content == ""
    assert note.agent == ""


def test_update_quick_note_then_get_returns_latest(conn):
    board.update_quick_note(conn, "call the dentist", "hope")

    note = board.get_quick_note(conn)

    assert note.content == "call the dentist"
    assert note.agent == "hope"


def test_update_quick_note_overwrites_previous_content(conn):
    board.update_quick_note(conn, "first note", "hope")
    board.update_quick_note(conn, "second note", "atlas")

    note = board.get_quick_note(conn)

    assert note.content == "second note"
    assert note.agent == "atlas"

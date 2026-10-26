"""Unit tests for the Board facade (memory/board/board.py wiring)."""

import pytest

from memory.board.store import Board

pytestmark = pytest.mark.unit


@pytest.fixture
def store(tmp_path):
    b = Board(db_path=tmp_path / "board.db")
    yield b
    b.close()


def test_add_item_round_trips(store):
    item = store.add_item("today", "buy milk", "hope")
    assert item.list_type == "today"
    assert item.done is False


def test_toggle_item_round_trips(store):
    item = store.add_item("today", "buy milk", "hope")

    toggled = store.toggle_item(item.id, "atlas")

    assert toggled.done is True
    assert toggled.agent == "atlas"


def test_update_item_text_round_trips(store):
    item = store.add_item("today", "buy milk", "hope")

    updated = store.update_item_text(item.id, "buy oat milk", "atlas")

    assert updated.text == "buy oat milk"


def test_delete_item_round_trips(store):
    item = store.add_item("today", "buy milk", "hope")

    assert store.delete_item(item.id) is True
    assert store.list_items("today") == []


def test_list_items_round_trips(store):
    item = store.add_item("planned", "dentist", "hope")

    items = store.list_items("planned")

    assert [i.id for i in items] == [item.id]


def test_quick_note_round_trips(store):
    store.update_quick_note("call the dentist", "hope")

    note = store.get_quick_note()

    assert note.content == "call the dentist"
    assert note.agent == "hope"

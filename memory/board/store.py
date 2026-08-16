"""Board facade — the only thing tool handlers (and the dashboard) touch for
the shared board. Same shape as memory/coordination/store.py:Blackboard.
"""

from pathlib import Path

from memory.board import board
from memory.board.schema import BoardItem, ListType, QuickNote
from settings import settings


class Board:
    def __init__(self, db_path: str | Path | None = None):
        self._conn = board.connect(db_path or settings.board_db_path)

    def add_item(self, list_type: ListType, text: str, agent: str) -> BoardItem:
        return board.add_item(self._conn, list_type, text, agent)

    def update_item_text(self, item_id: int, text: str, agent: str) -> BoardItem | None:
        return board.update_item_text(self._conn, item_id, text, agent)

    def toggle_item(self, item_id: int, agent: str) -> BoardItem | None:
        return board.toggle_item(self._conn, item_id, agent)

    def delete_item(self, item_id: int) -> bool:
        return board.delete_item(self._conn, item_id)

    def list_items(self, list_type: ListType) -> list[BoardItem]:
        return board.list_items(self._conn, list_type)

    def get_quick_note(self) -> QuickNote:
        return board.get_quick_note(self._conn)

    def update_quick_note(self, content: str, agent: str) -> QuickNote:
        return board.update_quick_note(self._conn, content, agent)

    def close(self) -> None:
        self._conn.close()

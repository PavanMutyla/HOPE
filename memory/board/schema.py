"""Typed records for the shared board, read back out of SQLite by board.py.
`memory/board/migrations/0001_init.sql` is the source of truth for column
shape; these models are the strict, immutable read contract on top of it —
same pattern as memory/coordination/schema.py.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

ListType = Literal["today", "planned", "pending"]


class BoardItem(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    id: int
    list_type: ListType
    text: str
    done: bool
    agent: str
    created_at: str
    updated_at: str


class QuickNote(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    content: str
    agent: str
    updated_at: str

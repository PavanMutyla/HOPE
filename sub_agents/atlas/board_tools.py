"""Atlas's adapter onto the shared board. Atlas's tool-execution loop
(`Atlas._execute_tool`) calls every dispatched tool as `fn(self._workspace,
**args)`, so every function here accepts (and ignores) `workspace` to keep
that call site uniform. The real logic lives in memory/board/store.py and
memory/board/live.py — the same functions HOPE's pipecat handlers in
tools/registry.py call — this file is only the thin adapter, matching
docs/HOPE_Dashboard_Design.md gap #4's plain-callable-business-logic pattern.
"""

from pathlib import Path

from memory.board import live as board_live
from memory.board.store import Board

_board = Board()

_AGENT = "atlas"


async def add_task(workspace: Path, list_type: str, text: str) -> str:
    item = _board.add_item(list_type, text, _AGENT)
    return f"Added to {list_type} (id {item.id}): {item.text}"


async def update_task(workspace: Path, item_id: int, text: str) -> str:
    item = _board.update_item_text(item_id, text, _AGENT)
    if item is None:
        return f"No task found with id {item_id}."
    return f"Updated task {item.id}: {item.text}"


async def toggle_task(workspace: Path, item_id: int) -> str:
    item = _board.toggle_item(item_id, _AGENT)
    if item is None:
        return f"No task found with id {item_id}."
    return f"Task {item.id} is now {'done' if item.done else 'not done'}."


async def delete_task(workspace: Path, item_id: int) -> str:
    deleted = _board.delete_item(item_id)
    return f"Deleted task {item_id}." if deleted else f"No task found with id {item_id}."


async def get_tasks(workspace: Path, list_type: str) -> str:
    items = _board.list_items(list_type)
    if not items:
        return f"Nothing on the {list_type} list."
    return "\n".join(
        f"- ({item.id}) {item.text} [{'done' if item.done else 'not done'}, {item.agent}]"
        for item in items
    )


async def get_quick_note(workspace: Path) -> str:
    note = _board.get_quick_note()
    return note.content or "Quick notes is empty."


async def update_quick_note(workspace: Path, content: str) -> str:
    _board.update_quick_note(content, _AGENT)
    return "Quick notes updated."


async def get_location_and_time(workspace: Path) -> str:
    info = await board_live.get_location_and_time()
    return f"{info['city']} ({info['lat']}, {info['lon']}) — {info['local_time']} on {info['local_date']}."


async def get_weather(workspace: Path) -> str:
    w = await board_live.get_weather()
    return (
        f"{w['temp_c']}°C, {w['condition']}. High {w['hi_c']}°, low {w['lo_c']}°, "
        f"wind {w['wind_kmh']} km/h."
    )


BOARD_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": (
                "Add an item to the shared board's Today, Planned, or Pending list — "
                "visible to Pavan and every agent, not just you."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "list_type": {
                        "type": "string",
                        "enum": ["today", "planned", "pending"],
                        "description": "Which board list to add to.",
                    },
                    "text": {"type": "string", "description": "The task text."},
                },
                "required": ["list_type", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Change the text of an existing board task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer", "description": "The task's id."},
                    "text": {"type": "string", "description": "The new text for the task."},
                },
                "required": ["item_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_task",
            "description": "Mark a board task done, or undone if it's already done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer", "description": "The task's id."},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Remove an item from the board entirely.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer", "description": "The task's id."},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tasks",
            "description": "Read the current items on one of the board's Today, Planned, or Pending lists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "list_type": {
                        "type": "string",
                        "enum": ["today", "planned", "pending"],
                        "description": "Which board list to read.",
                    },
                },
                "required": ["list_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_quick_note",
            "description": "Read the shared board's Quick notes.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_quick_note",
            "description": (
                "Replace the shared board's Quick notes with new content. This "
                "overwrites the whole note, so read it first with get_quick_note if "
                "you want to add to what's already there rather than replace it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The full new content."},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_location_and_time",
            "description": "Get Pavan's home location and the current local date/time.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather and today's forecast at Pavan's home location.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

BOARD_TOOL_DISPATCH = {
    "add_task": add_task,
    "update_task": update_task,
    "toggle_task": toggle_task,
    "delete_task": delete_task,
    "get_tasks": get_tasks,
    "get_quick_note": get_quick_note,
    "update_quick_note": update_quick_note,
    "get_location_and_time": get_location_and_time,
    "get_weather": get_weather,
}

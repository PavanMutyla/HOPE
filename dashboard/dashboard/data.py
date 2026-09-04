"""Static layout for the corkboard notes.

Position, paper colour, tape/pin and rotation live here; the *content* of every
note comes from the shared board at runtime (memory/board/), merged in by
DashboardState.load_board(). Splitting it this way is what lets a note Pavan
dragged somewhere stay there across the refresh loop.

The prototype's chat fixtures (fake threads, fake agent roster, fake
attachments) were deleted when text chat was removed: conversations are now
read from episodic memory and the live feed, and HOPE takes voice input only.
"""

NOTE_LAYOUT = [
    {
        "id": "n1", "type": "location", "title": "Location",
        "paper": "#fdf3c4", "tape": "#f2e29a", "pin": "tape",
        "rotate": -2, "x": 40, "y": 40, "w": 240,
        "location_city": "", "location_detail": "", "location_time": "",
    },
    {
        "id": "n2", "type": "weather", "title": "Weather",
        "paper": "#d5ecfb", "tape": "#b9d7ec", "pin": "pin",
        "rotate": 2, "x": 290, "y": 40, "w": 230,
        "temp": "", "condition": "", "hi": "", "lo": "", "wind": "",
    },
    {
        "id": "n3", "type": "tasks", "list_type": "today", "title": "Today",
        "paper": "#ddf3d1", "tape": "#c4e3b6", "pin": "tape",
        "rotate": -1, "x": 40, "y": 250, "w": 240, "tasks": [],
    },
    {
        "id": "n4", "type": "tasks", "list_type": "planned", "title": "Planned",
        "paper": "#ebe0f9", "tape": "#d8caee", "pin": "pin",
        "rotate": 2.5, "x": 290, "y": 250, "w": 230, "tasks": [],
    },
    {
        "id": "n5", "type": "tasks", "list_type": "pending", "title": "Pending",
        "paper": "#fce3c0", "tape": "#f2cf9d", "pin": "tape",
        "rotate": -2.5, "x": 40, "y": 470, "w": 240, "tasks": [],
    },
    {
        "id": "n6", "type": "notes", "title": "Quick notes",
        "paper": "#fbd9ea", "tape": "#f0bdd8", "pin": "pin",
        "rotate": 1.5, "x": 290, "y": 470, "w": 230,
        "content": "", "note_agent": "",
    },
]

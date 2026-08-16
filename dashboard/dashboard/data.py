"""Mock fixtures for the HOPE dashboard — ported 1:1 from the Claude Design
prototype's initial `state` (Claude Design project 88211171-b981-4b80-8275-
c7f8e8a58320, `HOPE Dashboard.dc.html`). Phase 1 is UI-only: no backend, no
persistence — matches docs/HOPE_Dashboard_Design.md's scope for this phase.
"""

AGENT_META = {
    "HOPE": {"color": "oklch(0.72 0.15 305)", "initial": "H"},
    "Scout": {"color": "oklch(0.75 0.14 150)", "initial": "S"},
    "Ledger": {"color": "oklch(0.78 0.15 70)", "initial": "L"},
}

MODEL_OPTIONS = ["HOPE", "Scout", "Ledger"]
ATTACH_TYPES = ["Image", "Document", "Audio", "Link"]
MOCK_ATTACHMENT_NAMES = {
    "Image": "photo.jpg",
    "Document": "notes.pdf",
    "Audio": "memo.m4a",
    "Link": "reference-link",
}

INITIAL_NOTES = [
    {
        "id": "n1", "type": "location", "title": "Location",
        "paper": "#fdf3c4", "tape": "#f2e29a", "pin": "tape",
        "rotate": -2, "x": 40, "y": 40, "w": 240,
        "location_city": "Austin, TX",
        "location_detail": "home network · 30.27N, 97.74W",
    },
    {
        "id": "n2", "type": "weather", "title": "Weather",
        "paper": "#d5ecfb", "tape": "#b9d7ec", "pin": "pin",
        "rotate": 2, "x": 290, "y": 40, "w": 230,
        "temp": "81°F", "condition": "Partly Cloudy",
        "hi": "88°", "lo": "71°", "wind": "6mph NW",
    },
    {
        "id": "n3", "type": "tasks", "title": "Today",
        "paper": "#ddf3d1", "tape": "#c4e3b6", "pin": "tape",
        "rotate": -1, "x": 40, "y": 250, "w": 240,
        "tasks": [
            {"text": "Morning run · 7am", "done": True},
            {"text": "Review Q3 budget draft", "done": True},
            {"text": "Team standup · 10:30am", "done": False},
            {"text": "Pick up dry cleaning", "done": False},
        ],
    },
    {
        "id": "n4", "type": "tasks", "title": "Planned",
        "paper": "#ebe0f9", "tape": "#d8caee", "pin": "pin",
        "rotate": 2.5, "x": 290, "y": 250, "w": 230,
        "tasks": [
            {"text": "Dentist · Thu 2pm", "done": False},
            {"text": "Denver trip · Oct 14-17", "done": False},
            {"text": "Mom's birthday · Aug 9", "done": False},
        ],
    },
    {
        "id": "n5", "type": "tasks", "title": "Pending",
        "paper": "#fce3c0", "tape": "#f2cf9d", "pin": "tape",
        "rotate": -2.5, "x": 40, "y": 470, "w": 240,
        "tasks": [
            {"text": "Reply to landlord re: lease", "done": False},
            {"text": "Approve invoice #2291", "done": False},
            {"text": "Book flight for conference", "done": False},
        ],
    },
    {
        "id": "n6", "type": "notes", "title": "Quick notes",
        "paper": "#fbd9ea", "tape": "#f0bdd8", "pin": "pin",
        "rotate": 1.5, "x": 290, "y": 470, "w": 230,
        "content": (
            "Ask HOPE to compare flight prices before Friday. "
            "Try the new ramen place near 6th St."
        ),
    },
]

INITIAL_CHATS = [
    {
        "id": "c1", "title": "Denver trip itinerary", "time": "2h",
        "dot": "oklch(0.78 0.14 200)",
        "messages": [
            {
                "id": "m1", "role": "user",
                "text": "Can you help me plan a 3 day trip to Denver in October?",
            },
            {
                "id": "m2", "role": "assistant", "agent": "Scout", "active_version": 0,
                "versions": [
                    "Sure — here's a solid 3-day outline: Day 1 arrive + explore "
                    "RiNo district, Day 2 Rocky Mountain National Park day trip, "
                    "Day 3 downtown + Union Station before your flight.",
                    "Alternative plan leaning into hiking: Day 1 easy acclimation "
                    "walk around Cherry Creek, Day 2 full day hike at Mount Falcon, "
                    "Day 3 recovery brunch + Denver Art Museum.",
                ],
            },
            {
                "id": "m3", "role": "user",
                "text": "Make day 2 more relaxed, I don't want a full hike.",
            },
            {
                "id": "m4", "role": "assistant", "agent": "HOPE", "active_version": 0,
                "versions": [
                    "Got it — swap Day 2 for a relaxed loop: Denver Botanic "
                    "Gardens in the morning, lunch in Cherry Creek, then a short "
                    "scenic drive up Lookout Mountain for sunset.",
                ],
            },
        ],
    },
    {
        "id": "c2", "title": "Debug useEffect loop", "time": "5h",
        "dot": "oklch(0.72 0.16 305)",
        "messages": [
            {
                "id": "m1", "role": "user",
                "text": "My useEffect keeps re-firing infinitely, any idea why?",
            },
            {
                "id": "m2", "role": "assistant", "agent": "Ledger", "active_version": 0,
                "versions": [
                    "Most likely an object or function recreated on every render "
                    "is in your dependency array. Wrap it in useCallback/useMemo, "
                    "or move it outside the component.",
                ],
            },
        ],
    },
    {
        "id": "c3", "title": "Weekly meal plan", "time": "1d",
        "dot": "oklch(0.75 0.14 150)",
        "messages": [
            {
                "id": "m1", "role": "user",
                "text": "Put together a simple high-protein meal plan for the week.",
            },
            {
                "id": "m2", "role": "assistant", "agent": "HOPE", "active_version": 0,
                "versions": [
                    "Here's a 5-day plan: rotating chicken/eggs/greek yogurt "
                    "bases, lean beef twice, salmon once, with overnight oats "
                    "for breakfast each day.",
                ],
            },
        ],
    },
    {
        "id": "c4", "title": "Server migration checklist", "time": "3d",
        "dot": "oklch(0.78 0.15 70)",
        "messages": [
            {
                "id": "m1", "role": "user",
                "text": "What should I check before migrating the prod DB this weekend?",
            },
            {
                "id": "m2", "role": "assistant", "agent": "Ledger", "active_version": 0,
                "versions": [
                    "Checklist: full backup + restore test, freeze writes window, "
                    "verify replica lag is zero, confirm rollback script, and "
                    "alert the on-call channel before starting.",
                ],
            },
        ],
    },
]

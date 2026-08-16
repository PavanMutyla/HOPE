import reflex as rx

from dashboard import styles as s
from dashboard.components.primitives import pointer_div
from dashboard.state import DashboardState

# Board rows store the raw agent_state.active value ("hope"/"atlas") or
# settings.user_name for dashboard-direct edits — display nicely without
# changing what's stored, so it stays consistent with agent_state's own
# lowercase convention.
_AGENT_DISPLAY = {"hope": "HOPE", "atlas": "Atlas"}


def _display_agent(agent: rx.Var[str]) -> rx.Var[str]:
    return rx.cond(
        agent == "hope", _AGENT_DISPLAY["hope"],
        rx.cond(agent == "atlas", _AGENT_DISPLAY["atlas"], agent),
    )


def _task_row(task: rx.Var[dict], idx: rx.Var[int]) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.cond(task["done"], "✓", ""),
            style={
                "width": "15px", "height": "15px", "borderRadius": "2px",
                "border": f"1.5px solid {s.INK}",
                "background": rx.cond(task["done"], "oklch(0.25 0.02 60 / 0.25)", "transparent"),
                "flexShrink": 0, "marginTop": "3px", "opacity": 0.85,
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "fontSize": "11px", "color": s.INK, "fontWeight": 700,
            },
        ),
        rx.el.div(
            f"{task['text']} ({_display_agent(task['agent'])})",
            style={
                "fontSize": "19px", "lineHeight": 1.2,
                "opacity": rx.cond(task["done"], 0.55, 1),
                "textDecoration": rx.cond(task["done"], "line-through", "none"),
            },
        ),
        on_click=DashboardState.toggle_task(task["id"]),
        style={"display": "flex", "alignItems": "flex-start", "gap": "8px", "padding": "4px 0", "cursor": "pointer"},
    )


def _note_body(note: rx.Var[dict]) -> rx.Component:
    return rx.el.div(
        rx.cond(
            note["type"] == "location",
            rx.fragment(
                rx.el.div(note["location_city"], style={"fontSize": "23px", "fontWeight": 600}),
                rx.el.div(note["location_detail"], style={"fontSize": "17px", "opacity": 0.75, "marginTop": "2px"}),
                rx.el.div(note["location_time"], style={"fontSize": "16px", "opacity": 0.7, "marginTop": "6px"}),
            ),
        ),
        rx.cond(
            note["type"] == "weather",
            rx.fragment(
                rx.el.div(
                    rx.el.div(note["temp"], style={"fontSize": "33px", "fontWeight": 700}),
                    rx.el.div(note["condition"], style={"fontSize": "18px", "opacity": 0.8}),
                    style={"display": "flex", "alignItems": "baseline", "gap": "8px"},
                ),
                rx.el.div(
                    rx.el.span(f"H {note['hi']}"),
                    rx.el.span(f"L {note['lo']}"),
                    rx.el.span(note["wind"]),
                    style={"fontSize": "16px", "opacity": 0.7, "marginTop": "2px", "display": "flex", "gap": "14px"},
                ),
            ),
        ),
        rx.cond(
            note["type"] == "tasks",
            rx.foreach(note["tasks"].to(list[dict]), _task_row),
        ),
        rx.cond(
            note["type"] == "notes",
            rx.fragment(
                rx.debounce_input(
                    rx.el.textarea(
                        value=note["content"],
                        on_change=DashboardState.edit_note_content,
                        placeholder="jot something down...",
                        style={
                            "width": "100%", "minHeight": "90px", "background": "transparent",
                            "border": "none", "outline": "none", "resize": "vertical",
                            "fontFamily": s.FONT_HAND, "fontSize": "19px", "color": s.INK, "lineHeight": 1.3,
                        },
                    ),
                    debounce_timeout=300,
                ),
                rx.cond(
                    note["note_agent"] != "",
                    rx.el.div(
                        f"last edited by {_display_agent(note['note_agent'])}",
                        style={"fontSize": "13px", "opacity": 0.55, "marginTop": "4px"},
                    ),
                ),
            ),
        ),
        style={"padding": "2px 18px 18px", "fontFamily": s.FONT_HAND, "color": s.INK, "userSelect": "text", "cursor": "text"},
    )


def _note_card(note: rx.Var[dict]) -> rx.Component:
    return rx.el.div(
        rx.cond(
            note["pin"] == "tape",
            rx.el.div(
                style={
                    "position": "absolute", "top": "-11px", "left": "50%",
                    "transform": "translateX(-50%) rotate(-2deg)", "width": "64px", "height": "22px",
                    "background": note["tape"], "opacity": 0.8, "boxShadow": "0 2px 4px oklch(0.05 0 0 / 0.25)",
                },
            ),
        ),
        rx.cond(
            note["pin"] == "pin",
            rx.el.div(
                style={
                    "position": "absolute", "top": "-7px", "left": "50%", "transform": "translateX(-50%)",
                    "width": "13px", "height": "13px", "borderRadius": "50%",
                    "background": "radial-gradient(circle at 35% 30%, #ff8a7a, #c0392b)",
                    "boxShadow": "0 3px 5px oklch(0.05 0 0 / 0.45)",
                },
            ),
        ),
        pointer_div(
            note["title"],
            on_mouse_down=DashboardState.start_note_drag(note["id"]),
            style={"padding": "16px 18px 4px", "cursor": "grab", "fontFamily": s.FONT_HAND, "fontSize": "20px", "fontWeight": 700, "color": s.INK, "userSelect": "none"},
        ),
        _note_body(note),
        style={
            "position": "absolute",
            "left": f"{note['x']}px", "top": f"{note['y']}px",
            "width": f"{note['w']}px", "minHeight": "180px",
            "background": note["paper"],
            "backgroundImage": (
                "linear-gradient(oklch(1 0 0 / 0.15), transparent 45%), "
                "repeating-linear-gradient(115deg, oklch(0 0 0 / 0.035) 0px, "
                "oklch(0 0 0 / 0.035) 1px, transparent 1px, transparent 3px)"
            ),
            "transform": f"rotate({note['rotate']}deg)",
            "borderRadius": "2px",
            "boxShadow": (
                "0 18px 30px oklch(0.05 0 0 / 0.5), 0 4px 8px oklch(0.05 0 0 / 0.35), "
                "inset 0 0 40px oklch(0 0 0 / 0.05)"
            ),
        },
    )


def corkboard() -> rx.Component:
    return rx.el.div(
        rx.foreach(DashboardState.notes, _note_card),
        style={
            "position": "absolute",
            "left": rx.cond(DashboardState.sidebar_collapsed, "64px", "260px"),
            "right": 0, "top": 0, "bottom": 0, "overflow": "auto",
            "transition": "left 0.2s ease",
            "backgroundColor": s.CANVAS_BG,
            "backgroundImage": "radial-gradient(circle, oklch(0.27 0.012 255) 1px, transparent 1px)",
            "backgroundSize": "26px 26px",
        },
    )

"""Log cards: three views of HOPE's log file.

- Log: the raw tail, everything the process writes.
- Tools: every tool HOPE or Atlas calls, and how long it took to answer.
- Web: searches, pages read and researchers spawned, as they happen.

This is machine output, so it is the one surface that stays monospace and dense
on purpose. The Tools and Web cards drop loguru's prefix down to a time and the
message, since the card's name already says what kind of line it is.
"""

import reflex as rx

from dashboard import styles as s
from dashboard.components.primitives import pointer_div
from dashboard.state import DashboardState


def _log_line(line: rx.Var[str]) -> rx.Component:
    return rx.el.div(line, style={"whiteSpace": "pre-wrap", "wordBreak": "break-word"})


def _activity_row(row: rx.Var[dict]) -> rx.Component:
    return rx.el.div(
        rx.el.span(row["time"], class_name="tabular", style={"color": s.TEXT_MUTED}),
        rx.el.span(
            row["text"],
            # Warnings (a blocked page, a failed search) step up the text ramp
            # rather than taking a color: the accent is locked to the product.
            style={
                "color": rx.cond(row["warn"] != "", s.TEXT, s.TEXT_DIM),
                "whiteSpace": "pre-wrap", "wordBreak": "break-word", "minWidth": 0,
            },
        ),
        style={"display": "grid", "gridTemplateColumns": "auto 1fr", "gap": "10px"},
    )


def _activity(rows: rx.Var[list[dict]], empty: str) -> rx.Component:
    return rx.cond(
        rows.length() > 0,
        rx.foreach(rows, _activity_row),
        rx.el.p(empty, style={"margin": 0, "color": s.TEXT_MUTED}),
    )


def _log_card(
    card: str,
    title: str,
    label: str,
    body: rx.Component,
    width: str,
    height: str,
) -> rx.Component:
    return rx.cond(
        DashboardState.log_open[card],
        rx.el.section(
            rx.el.div(style=s.corner_bracket("top", "left")),
            rx.el.div(style=s.corner_bracket("bottom", "right")),
            pointer_div(
                rx.el.h2(
                    title,
                    id=f"log-card-{card}",
                    style={
                        "margin": 0, "fontFamily": s.FONT_MONO, "fontSize": s.SIZE_META,
                        "fontWeight": 600, "color": s.TEXT_DIM, "letterSpacing": "1px",
                    },
                ),
                rx.el.button(
                    "Close",
                    on_click=DashboardState.close_log(card),
                    aria_label=f"Close {title.lower()}",
                    style={
                        **s.GHOST_BUTTON, "marginLeft": "auto",
                        "_hover": {"color": s.TEXT},
                        "_focusVisible": s.FOCUS_RING,
                    },
                ),
                on_mouse_down=lambda info: DashboardState.start_log_drag(card, info),
                style={
                    "display": "flex", "alignItems": "center", "gap": "10px",
                    "padding": "10px 14px", "borderBottom": f"1px solid {s.BORDER}",
                    "cursor": "grab", "flexShrink": 0,
                },
            ),
            rx.auto_scroll(
                body,
                # Up to 200 rows that rewrite every 3 seconds; the classes contain
                # overscroll and let the browser skip offscreen line layout.
                class_name="panel-scroll virtual-rows",
                role="log",
                aria_label=label,
                style={
                    "flex": 1, "overflowY": "auto", "padding": "10px 14px",
                    "fontFamily": s.FONT_MONO, "fontSize": s.SIZE_MICRO,
                    "lineHeight": 1.55, "color": s.TEXT_DIM,
                },
            ),
            aria_labelledby=f"log-card-{card}",
            style={
                "position": "absolute",
                "left": f"{DashboardState.log_x[card]}px",
                "top": f"{DashboardState.log_y[card]}px",
                "width": width, "height": height,
                "background": s.PANEL_BG, "border": f"1px solid {s.BORDER}",
                "borderRadius": s.RADIUS,
                "boxShadow": "0 14px 34px oklch(0.10 0.01 255 / 0.45)",
                "display": "flex", "flexDirection": "column", "zIndex": 25,
            },
        ),
    )


def terminal_panel() -> rx.Component:
    return _log_card(
        "log", "Log", "HOPE log output",
        rx.foreach(DashboardState.terminal_lines, _log_line),
        width="min(500px, calc(100vw - 320px))", height="220px",
    )


def tools_panel() -> rx.Component:
    return _log_card(
        "tools", "Tools", "Tool calls by HOPE and Atlas",
        _activity(
            DashboardState.tool_rows,
            "No tool calls yet. Each one appears here when HOPE or Atlas uses a tool.",
        ),
        width="min(440px, calc(100vw - 320px))", height="300px",
    )


def web_panel() -> rx.Component:
    return _log_card(
        "web", "Web", "Web searches, pages read and researchers",
        _activity(
            DashboardState.web_rows,
            "No web activity yet. Ask HOPE to look something up or research a topic.",
        ),
        width="min(440px, calc(100vw - 320px))", height="300px",
    )

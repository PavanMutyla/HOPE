"""Tail of HOPE's log file.

This is machine output, so it is the one surface that stays monospace and dense
on purpose. It reports what the process is doing at a level the console
deliberately does not: tool dispatch, folds, errors.
"""

import reflex as rx

from dashboard import styles as s
from dashboard.components.primitives import pointer_div
from dashboard.state import DashboardState


def _log_line(line: rx.Var[str]) -> rx.Component:
    return rx.el.div(line, style={"whiteSpace": "pre-wrap", "wordBreak": "break-word"})


def terminal_panel() -> rx.Component:
    return rx.cond(
        DashboardState.terminal_open,
        rx.el.section(
            rx.el.div(style=s.corner_bracket("top", "left")),
            rx.el.div(style=s.corner_bracket("bottom", "right")),
            pointer_div(
                rx.el.h2(
                    "Log",
                    style={
                        "margin": 0, "fontFamily": s.FONT_MONO, "fontSize": s.SIZE_META,
                        "fontWeight": 600, "color": s.TEXT_DIM, "letterSpacing": "1px",
                    },
                ),
                rx.el.button(
                    "Close",
                    on_click=DashboardState.close_terminal,
                    style={
                        **s.GHOST_BUTTON, "marginLeft": "auto",
                        "_hover": {"color": s.TEXT},
                        "_focusVisible": s.FOCUS_RING,
                    },
                ),
                on_mouse_down=DashboardState.start_terminal_drag,
                style={
                    "display": "flex", "alignItems": "center", "gap": "10px",
                    "padding": "10px 14px", "borderBottom": f"1px solid {s.BORDER}",
                    "cursor": "grab", "flexShrink": 0,
                },
            ),
            rx.auto_scroll(
                rx.foreach(DashboardState.terminal_lines, _log_line),
                # 200 rows that rewrite every 3 seconds; the classes contain
                # overscroll and let the browser skip offscreen line layout.
                class_name="panel-scroll virtual-rows",
                role="log",
                aria_label="HOPE log output",
                style={
                    "flex": 1, "overflowY": "auto", "padding": "10px 14px",
                    "fontFamily": s.FONT_MONO, "fontSize": s.SIZE_MICRO,
                    "lineHeight": 1.55, "color": s.TEXT_DIM,
                },
            ),
            style={
                "position": "absolute",
                "left": f"{DashboardState.terminal_x}px",
                "top": f"{DashboardState.terminal_y}px",
                "width": "min(500px, calc(100vw - 320px))", "height": "220px",
                "background": s.PANEL_BG, "border": f"1px solid {s.BORDER}",
                "borderRadius": s.RADIUS,
                "boxShadow": "0 14px 34px oklch(0.10 0.01 255 / 0.45)",
                "display": "flex", "flexDirection": "column", "zIndex": 25,
            },
        ),
    )

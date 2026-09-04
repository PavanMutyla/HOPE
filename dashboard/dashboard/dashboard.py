"""HOPE dashboard.

A read-only view of one voice agent: the shared board it edits, the
conversation it is having now, and the conversations it has had. Input is
voice, through hope.py; nothing here types at HOPE.
"""

import reflex as rx

from dashboard import styles as s
from dashboard.components.console import console
from dashboard.components.corkboard import corkboard
from dashboard.components.primitives import pointer_div
from dashboard.components.sidebar import sidebar
from dashboard.components.terminal_panel import terminal_panel
from dashboard.state import DashboardState

_BASE_CSS = """
* { box-sizing: border-box; }
/* Dark-only product: this is what makes scrollbars and native form controls
   render dark instead of light-on-dark. */
html { color-scheme: dark; }
::selection { background: oklch(0.78 0.14 200 / 0.3); }
/* No double-tap zoom delay on the drag surfaces. */
body { touch-action: manipulation; -webkit-tap-highlight-color: transparent; }
/* Timestamps, counts and percentages sit in columns and change in place, so
   they need fixed-width figures or the layout jitters as they update. */
.tabular { font-variant-numeric: tabular-nums; }
/* A scroll inside a panel should not chain to the page behind it. */
.panel-scroll { overscroll-behavior: contain; }
/* Long logs and transcripts: skip layout work for offscreen rows. */
.virtual-rows > * { content-visibility: auto; contain-intrinsic-size: auto 24px; }
.skip-link {
  position: absolute; left: 8px; top: -48px; z-index: 100;
  padding: 8px 12px; border-radius: 5px;
  background: oklch(0.185 0.014 255); color: oklch(0.93 0.006 255);
  border: 1px solid oklch(0.78 0.14 200); font-size: 12px;
  transition: top 0.15s ease;
}
.skip-link:focus { top: 8px; }
/* Text selection fights pointer-drag; suppressed only while a drag runs. */
body.dragging, body.dragging * { user-select: none !important; }
"""


def _reopen_bar() -> rx.Component:
    """Closing a panel has to be undoable. The prototype's close buttons were
    one-way: nothing brought the panel back short of reloading the page."""
    return rx.el.div(
        rx.cond(
            ~DashboardState.console_open,
            rx.el.button(
                "Show conversation",
                on_click=DashboardState.open_console,
                style={
                    "fontSize": s.SIZE_MICRO, "fontFamily": s.FONT_MONO,
                    "padding": "7px 12px", "borderRadius": s.RADIUS,
                    "border": f"1px solid {s.BORDER_STRONG}",
                    "background": s.PANEL_BG, "color": s.TEXT_DIM, "cursor": "pointer",
                    "_hover": {"color": s.TEXT, "borderColor": s.ACCENT},
                    "_focusVisible": s.FOCUS_RING,
                },
            ),
        ),
        rx.cond(
            ~DashboardState.terminal_open,
            rx.el.button(
                "Show log",
                on_click=DashboardState.open_terminal,
                style={
                    "fontSize": s.SIZE_MICRO, "fontFamily": s.FONT_MONO,
                    "padding": "7px 12px", "borderRadius": s.RADIUS,
                    "border": f"1px solid {s.BORDER_STRONG}",
                    "background": s.PANEL_BG, "color": s.TEXT_DIM, "cursor": "pointer",
                    "_hover": {"color": s.TEXT, "borderColor": s.ACCENT},
                    "_focusVisible": s.FOCUS_RING,
                },
            ),
        ),
        style={
            "position": "absolute", "right": "16px", "bottom": "16px",
            "display": "flex", "gap": "8px", "zIndex": 40,
        },
    )


def index() -> rx.Component:
    return pointer_div(
        rx.el.style(_BASE_CSS),
        rx.el.a("Skip to content", href="#board", class_name="skip-link"),
        # The page needs exactly one h1. It is visually redundant next to the
        # brand mark in the rail, so it is available to screen readers only
        # rather than duplicated on screen.
        rx.el.h1(
            "HOPE dashboard",
            style={
                "position": "absolute", "width": "1px", "height": "1px",
                "overflow": "hidden", "clip": "rect(0 0 0 0)",
                "clipPath": "inset(50%)", "whiteSpace": "nowrap",
            },
        ),
        sidebar(),
        rx.el.main(
            corkboard(),
            console(),
            terminal_panel(),
            id="board",
            style={"position": "absolute", "inset": 0},
        ),
        _reopen_bar(),
        on_mouse_move=DashboardState.on_root_mouse_move,
        on_mouse_up=DashboardState.on_root_mouse_up,
        on_mount=DashboardState.on_page_load,
        style={
            "position": "relative", "width": "100vw", "height": "100dvh",
            "overflow": "hidden", "background": s.BG,
            "fontFamily": s.FONT_SANS, "color": s.TEXT,
            "userSelect": rx.cond(DashboardState.is_dragging, "none", "auto"),
        },
    )


app = rx.App(
    stylesheets=["/styles.css"],
    head_components=[
        rx.el.meta(name="theme-color", content="#1b1d23"),
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(rel="preconnect", href="https://fonts.gstatic.com", cross_origin=""),
        rx.el.link(
            href=(
                "https://fonts.googleapis.com/css2"
                "?family=IBM+Plex+Sans:wght@400;500;600"
                "&family=IBM+Plex+Mono:wght@400;500;600"
                "&family=Caveat:wght@500;600;700"
                "&display=swap"
            ),
            rel="stylesheet",
        ),
    ],
)
app.add_page(index, title="HOPE")

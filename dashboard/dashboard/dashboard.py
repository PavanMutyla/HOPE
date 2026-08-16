"""HOPE dashboard — Phase 1 UI port (mock data, no backend). See
docs/HOPE_Dashboard_Design.md for scope; this is a faithful Reflex port of
the Claude Design prototype (`HOPE Dashboard.dc.html`)."""

import reflex as rx

from dashboard import styles as s
from dashboard.components.chat_panel import chat_panel
from dashboard.components.corkboard import corkboard
from dashboard.components.primitives import pointer_div
from dashboard.components.sidebar import sidebar
from dashboard.components.terminal_panel import terminal_panel
from dashboard.state import DashboardState


def index() -> rx.Component:
    return pointer_div(
        sidebar(),
        corkboard(),
        chat_panel(),
        terminal_panel(),
        on_mouse_move=DashboardState.on_root_mouse_move,
        on_mouse_up=DashboardState.on_root_mouse_up,
        on_mount=DashboardState.on_page_load,
        style={
            "position": "relative", "width": "100vw", "height": "100vh", "overflow": "hidden",
            "background": s.BG, "fontFamily": s.FONT_SANS, "color": s.TEXT, "userSelect": "none",
        },
    )


app = rx.App(
    stylesheets=["/styles.css"],
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Caveat:wght@500;600;700&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(index, title="HOPE Dashboard")

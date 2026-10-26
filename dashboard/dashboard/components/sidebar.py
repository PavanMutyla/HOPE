"""Left rail: what HOPE is doing now, above everything it has done before.

Live sits at the top as a pinned entry rather than a separate control, so the
console has one selection model instead of a mode toggle. The rule the list
follows: the archive holds finished conversations only, and the run in progress
is always Live, never a row.
"""

import reflex as rx

from dashboard import styles as s
from dashboard.state import DashboardState


def _status_dot() -> rx.Component:
    """The only dot in the product, and the only green. It reports whether the
    voice pipeline is actually up, which is real state and the single most
    important thing on the page."""
    return rx.el.span(
        style={
            "width": "7px", "height": "7px", "borderRadius": s.RADIUS_PILL,
            "flexShrink": 0,
            "background": rx.cond(DashboardState.hope_is_running, s.LIVE, s.TEXT_MUTED),
            "boxShadow": rx.cond(
                DashboardState.hope_is_running, f"0 0 0 3px {s.LIVE_SOFT}", "none"
            ),
        },
    )


def _live_entry() -> rx.Component:
    return rx.el.button(
        _status_dot(),
        rx.cond(
            ~DashboardState.sidebar_collapsed,
            rx.el.span(
                rx.el.span(
                    "Now",
                    style={"fontSize": s.SIZE_BODY, "fontWeight": 600, "color": s.TEXT},
                ),
                rx.el.span(
                    DashboardState.live_status_label,
                    style={
                        "fontFamily": s.FONT_MONO, "fontSize": s.SIZE_MICRO,
                        "color": rx.cond(
                            DashboardState.hope_is_running, s.LIVE, s.TEXT_MUTED
                        ),
                        "marginTop": "2px",
                    },
                ),
                style={
                    "display": "flex", "flexDirection": "column",
                    "alignItems": "flex-start", "minWidth": 0, "flex": 1,
                },
            ),
        ),
        on_click=DashboardState.select_live,
        aria_label="Show the current conversation",
        style={
            "display": "flex", "alignItems": "center", "gap": "10px", "width": "100%",
            "padding": "11px 10px", "borderRadius": s.RADIUS, "cursor": "pointer",
            "textAlign": "left", "fontFamily": s.FONT_SANS,
            "background": rx.cond(
                DashboardState.is_live_selected, s.ACCENT_SOFT, "transparent"
            ),
            "border": rx.cond(
                DashboardState.is_live_selected,
                f"1px solid {s.ACCENT}",
                f"1px solid {s.BORDER}",
            ),
            "_hover": {"background": s.PANEL_RAISED},
            "_focusVisible": s.FOCUS_RING,
        },
    )


def _thread_row(thread: rx.Var[dict]) -> rx.Component:
    return rx.el.button(
        rx.cond(
            DashboardState.sidebar_collapsed,
            rx.el.span(
                thread["ago"],
                style={
                    "fontFamily": s.FONT_MONO, "fontSize": s.SIZE_MICRO,
                    "color": s.TEXT_DIM, "width": "100%", "textAlign": "center",
                },
            ),
            rx.fragment(
                rx.el.span(
                    rx.el.span(
                        thread["headline"],
                        style={
                            "fontSize": s.SIZE_META, "fontWeight": 500, "color": s.TEXT,
                            "display": "block", "overflow": "hidden",
                            "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                        },
                    ),
                    rx.el.span(
                        thread["count_label"],
                        class_name="tabular",
                        style={
                            "fontFamily": s.FONT_MONO, "fontSize": s.SIZE_MICRO,
                            "color": s.TEXT_MUTED, "marginTop": "3px", "display": "block",
                        },
                    ),
                    style={"minWidth": 0, "flex": 1},
                ),
                rx.el.span(
                    thread["ago"],
                    class_name="tabular",
                    style={
                        "fontFamily": s.FONT_MONO, "fontSize": s.SIZE_MICRO,
                        "color": s.TEXT_MUTED, "flexShrink": 0, "alignSelf": "flex-start",
                    },
                ),
            ),
        ),
        on_click=DashboardState.select_thread(thread["id"]),
        style={
            "display": "flex", "alignItems": "center", "gap": "10px", "width": "100%",
            "padding": "10px", "borderRadius": s.RADIUS, "cursor": "pointer",
            "marginBottom": "2px", "textAlign": "left", "fontFamily": s.FONT_SANS,
            "background": rx.cond(thread["active"], s.ACCENT_SOFT, "transparent"),
            "border": rx.cond(
                thread["active"], f"1px solid {s.ACCENT}", "1px solid transparent"
            ),
            "_hover": {"background": s.PANEL_RAISED},
            "_focusVisible": s.FOCUS_RING,
        },
    )


def _empty_archive() -> rx.Component:
    return rx.el.p(
        "Conversations appear here once a session ends.",
        style={
            "fontSize": s.SIZE_MICRO, "color": s.TEXT_MUTED, "padding": "10px",
            "lineHeight": 1.5, "margin": 0,
        },
    )


def sidebar() -> rx.Component:
    return rx.el.aside(
        rx.el.div(style=s.corner_bracket("top", "right")),
        rx.el.div(style=s.corner_bracket("bottom", "right")),
        # brand
        rx.el.div(
            rx.el.span(
                style={
                    "width": "9px", "height": "9px", "borderRadius": "2px",
                    "background": s.ACCENT, "flexShrink": 0,
                },
            ),
            rx.cond(
                ~DashboardState.sidebar_collapsed,
                rx.el.span(
                    "HOPE",
                    style={
                        "fontFamily": s.FONT_MONO, "fontWeight": 600,
                        "fontSize": s.SIZE_BODY, "letterSpacing": "2px",
                        "color": s.TEXT,
                    },
                ),
            ),
            rx.el.button(
                rx.cond(DashboardState.sidebar_collapsed, "»", "«"),
                on_click=DashboardState.toggle_sidebar,
                aria_label=rx.cond(
                    DashboardState.sidebar_collapsed,
                    "Expand sidebar",
                    "Collapse sidebar",
                ),
                style={
                    "marginLeft": "auto", "width": "28px", "height": "28px",
                    "borderRadius": s.RADIUS, "border": f"1px solid {s.BORDER_STRONG}",
                    "background": s.PANEL_RAISED, "color": s.TEXT_DIM,
                    "cursor": "pointer", "fontSize": s.SIZE_BODY, "flexShrink": 0,
                    "display": "flex", "alignItems": "center", "justifyContent": "center",
                    "_hover": {"color": s.TEXT},
                    "_focusVisible": s.FOCUS_RING,
                },
            ),
            style={
                "display": "flex", "alignItems": "center", "gap": "10px",
                "padding": "16px 14px", "borderBottom": f"1px solid {s.BORDER}",
            },
        ),
        # now
        rx.el.div(_live_entry(), style={"padding": "12px 10px 10px"}),
        # archive
        rx.cond(
            ~DashboardState.sidebar_collapsed,
            rx.el.h2(
                "Earlier",
                style={
                    "fontSize": s.SIZE_MICRO, "fontWeight": 600, "color": s.TEXT_MUTED,
                    "margin": 0, "padding": "6px 12px 8px",
                    "borderTop": f"1px solid {s.BORDER}",
                },
            ),
        ),
        rx.el.div(
            rx.cond(
                DashboardState.sessions.length() > 0,
                rx.foreach(DashboardState.thread_rows, _thread_row),
                rx.cond(~DashboardState.sidebar_collapsed, _empty_archive()),
            ),
            class_name="panel-scroll",
            style={"flex": 1, "overflowY": "auto", "padding": "0 10px 12px"},
        ),
        style={
            "position": "absolute", "left": 0, "top": "12px", "bottom": "12px",
            "width": rx.cond(DashboardState.sidebar_collapsed, "68px", "268px"),
            "background": s.PANEL_BG, "border": f"1px solid {s.BORDER}",
            "borderLeft": "none", "borderRadius": f"0 {s.RADIUS} {s.RADIUS} 0",
            "display": "flex", "flexDirection": "column",
            "transition": "width 0.18s ease", "zIndex": 20,
        },
    )

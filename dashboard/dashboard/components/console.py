"""The console: one conversation, read only.

It shows either the conversation happening now or one that already finished,
depending on what is selected in the rail. There is no compose bar and no send
button anywhere, and that absence is deliberate rather than unfinished. HOPE
takes voice input only, so an input affordance here would promise something
that does not exist.

The two modes share one message list. A live turn and a stored turn are the
same thing at different ages, so DashboardState.console_messages normalizes
both into one shape and this file never branches on which it is rendering.
"""

import reflex as rx

from dashboard import styles as s
from dashboard.components.primitives import pointer_div
from dashboard.state import DashboardState

# The one animation in the product. It carries real state (the pipeline is up
# and listening) and stops the moment that stops being true, so it is never
# decoration. Reduced motion collapses it to a static dot.
_PULSE_KEYFRAMES = """
@keyframes hope-listening {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.45; transform: scale(0.82); }
}
@media (prefers-reduced-motion: reduce) {
  .hope-listening { animation: none !important; }
}
"""


def _status_line() -> rx.Component:
    """Live only: what HOPE is doing, and how full its context is."""
    return rx.el.div(
        rx.el.span(
            className="hope-listening",
            style={
                "width": "7px", "height": "7px", "borderRadius": s.RADIUS_PILL,
                "background": rx.cond(DashboardState.hope_is_running, s.LIVE, s.TEXT_MUTED),
                "flexShrink": 0,
                "animation": rx.cond(
                    DashboardState.hope_is_running, "hope-listening 2s ease-in-out infinite", "none"
                ),
            },
        ),
        rx.el.span(
            DashboardState.live_status_label,
            style={
                "fontFamily": s.FONT_MONO, "fontSize": s.SIZE_MICRO,
                "color": rx.cond(DashboardState.hope_is_running, s.LIVE, s.TEXT_MUTED),
            },
        ),
        rx.cond(
            DashboardState.hope_is_running,
            rx.el.span(
                DashboardState.context_label,
                class_name="tabular",
                style={
                    "fontFamily": s.FONT_MONO, "fontSize": s.SIZE_MICRO,
                    "color": s.TEXT_MUTED, "marginLeft": "auto",
                },
            ),
        ),
        # The status changes on its own as HOPE listens, thinks and speaks.
        # Without a live region a screen reader never hears about any of it.
        aria_live="polite",
        style={
            "display": "flex", "alignItems": "center", "gap": "8px",
            "padding": "9px 14px", "borderBottom": f"1px solid {s.BORDER}",
            "background": rx.cond(DashboardState.hope_is_running, s.LIVE_SOFT, "transparent"),
        },
    )


def _message(message: rx.Var[dict]) -> rx.Component:
    """Speaker name above the text rather than an avatar chip beside it: with
    only two participants, a name reads faster than a coloured initial, and it
    stays legible when a turn is one word long."""
    return rx.el.div(
        rx.el.div(
            message["speaker"],
            style={
                "fontFamily": s.FONT_MONO, "fontSize": s.SIZE_MICRO,
                "letterSpacing": "0.5px", "marginBottom": "4px",
                "color": rx.cond(message["is_user"], s.TEXT_MUTED, s.ACCENT),
            },
        ),
        rx.el.p(
            message["text"],
            style={
                "margin": 0, "fontSize": s.SIZE_BODY, "lineHeight": 1.6,
                "color": rx.cond(message["is_user"], s.TEXT_DIM, s.TEXT),
                "whiteSpace": "pre-wrap", "overflowWrap": "anywhere",
            },
        ),
        style={
            "padding": "10px 12px", "borderRadius": s.RADIUS, "maxWidth": "62ch",
            "marginLeft": rx.cond(message["is_user"], "auto", "0"),
            "background": rx.cond(message["is_user"], s.PANEL_RAISED, "transparent"),
            "borderLeft": rx.cond(message["is_user"], "none", f"2px solid {s.ACCENT}"),
        },
    )


def _empty() -> rx.Component:
    return rx.el.div(
        rx.el.p(
            DashboardState.empty_message,
            style={
                "margin": 0, "fontSize": s.SIZE_META, "color": s.TEXT_MUTED,
                "lineHeight": 1.6, "maxWidth": "34ch", "textAlign": "center",
            },
        ),
        style={
            "flex": 1, "display": "flex", "alignItems": "center",
            "justifyContent": "center", "padding": "32px 20px",
        },
    )


def _loading() -> rx.Component:
    """Skeleton shaped like the transcript it replaces, so the panel does not
    jump when the real content lands."""
    return rx.el.div(
        *[
            rx.el.div(
                style={
                    "height": "13px", "borderRadius": "3px",
                    "background": s.PANEL_RAISED,
                    "width": width, "marginBottom": "10px",
                    "marginLeft": "auto" if i % 2 else "0",
                },
            )
            for i, width in enumerate(["44%", "62%", "38%", "56%"])
        ],
        style={"padding": "18px 14px"},
    )


def console() -> rx.Component:
    return rx.cond(
        DashboardState.console_open,
        pointer_div(
            rx.el.style(_PULSE_KEYFRAMES),
            rx.el.div(style=s.corner_bracket("top", "left")),
            rx.el.div(style=s.corner_bracket("bottom", "right")),
            # header, and the drag handle
            pointer_div(
                rx.el.h2(
                    DashboardState.console_title,
                    style={
                        "margin": 0, "fontSize": s.SIZE_TITLE, "fontWeight": 600,
                        "color": s.TEXT, "overflow": "hidden",
                        "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                    },
                ),
                rx.el.button(
                    "Close",
                    on_click=DashboardState.close_console,
                    style={
                        **s.GHOST_BUTTON, "marginLeft": "auto",
                        "_hover": {"color": s.TEXT},
                        "_focusVisible": s.FOCUS_RING,
                    },
                ),
                on_mouse_down=DashboardState.start_console_drag,
                style={
                    "display": "flex", "alignItems": "center", "gap": "10px",
                    "padding": "12px 14px", "borderBottom": f"1px solid {s.BORDER}",
                    "cursor": "grab",
                },
            ),
            rx.cond(DashboardState.is_live_selected, _status_line()),
            rx.cond(
                DashboardState.transcript_loading,
                _loading(),
                rx.cond(
                    DashboardState.console_is_empty,
                    _empty(),
                    rx.el.div(
                        rx.foreach(DashboardState.console_messages, _message),
                        class_name="panel-scroll virtual-rows",
                        style={
                            "flex": 1, "overflowY": "auto", "padding": "14px",
                            "display": "flex", "flexDirection": "column", "gap": "14px",
                        },
                    ),
                ),
            ),
            style={
                "position": "absolute",
                "left": f"{DashboardState.console_x}px",
                "top": f"{DashboardState.console_y}px",
                "width": "min(560px, calc(100vw - 320px))",
                "height": "min(600px, calc(100vh - 96px))",
                "display": "flex", "flexDirection": "column",
                "background": s.PANEL_BG, "border": f"1px solid {s.BORDER}",
                "borderRadius": s.RADIUS, "zIndex": 30,
                "boxShadow": "0 18px 48px oklch(0.10 0.01 255 / 0.5)",
            },
        ),
    )

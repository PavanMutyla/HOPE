import reflex as rx

from dashboard import styles as s
from dashboard.state import DashboardState


def _chat_row(chat: rx.Var[dict]) -> rx.Component:
    return rx.el.div(
        rx.cond(
            DashboardState.sidebar_collapsed,
            rx.el.div(
                chat["initial"],
                style={
                    "width": "22px", "height": "22px", "borderRadius": "6px",
                    "background": "oklch(0.28 0.016 255)", "color": "oklch(0.75 0.01 255)",
                    "fontFamily": s.FONT_MONO, "fontSize": "11px", "fontWeight": 600,
                    "display": "flex", "alignItems": "center", "justifyContent": "center",
                    "flexShrink": 0,
                },
            ),
        ),
        rx.cond(
            ~DashboardState.sidebar_collapsed,
            rx.fragment(
                rx.el.div(
                    rx.el.div(
                        chat["title"],
                        style={
                            "fontSize": "12.5px", "fontWeight": 500, "color": "oklch(0.9 0.006 255)",
                            "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis",
                        },
                    ),
                    rx.el.div(
                        chat["preview"],
                        style={
                            "fontSize": "10.5px", "fontFamily": s.FONT_MONO, "color": s.TEXT_DIMMER,
                            "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis",
                            "marginTop": "2px",
                        },
                    ),
                    style={"minWidth": 0, "flex": 1},
                ),
                rx.el.div(
                    chat["time"],
                    style={"fontSize": "9.5px", "fontFamily": s.FONT_MONO, "color": "oklch(0.45 0.012 255)", "flexShrink": 0},
                ),
            ),
        ),
        on_click=DashboardState.select_chat(chat["id"]),
        style={
            "display": "flex", "alignItems": "center", "gap": "10px", "padding": "10px 9px",
            "borderRadius": "4px", "cursor": "pointer", "marginBottom": "3px",
            "background": rx.cond(chat["active"], "oklch(0.26 0.02 255)", "transparent"),
            "border": rx.cond(chat["active"], "1px solid oklch(0.4 0.03 255)", "1px solid transparent"),
        },
    )


def sidebar() -> rx.Component:
    return rx.el.div(
        rx.el.div(style=s.CORNER_BRACKET_TR),
        rx.el.div(style=s.CORNER_BRACKET_BR),
        rx.el.div(
            rx.el.div(style={"width": "9px", "height": "9px", "borderRadius": "2px", "background": s.ACCENT, "flexShrink": 0}),
            rx.cond(
                ~DashboardState.sidebar_collapsed,
                rx.el.div(
                    "HOPE ",
                    rx.el.span("// sys", style={"opacity": 0.4, "letterSpacing": "1px"}),
                    style={
                        "fontFamily": s.FONT_MONO, "fontWeight": 600, "fontSize": "13px",
                        "letterSpacing": "2.5px", "whiteSpace": "nowrap", "textTransform": "uppercase",
                    },
                ),
            ),
            rx.el.button(
                rx.cond(DashboardState.sidebar_collapsed, "»", "«"),
                on_click=DashboardState.toggle_sidebar,
                style={
                    "marginLeft": "auto", "width": "26px", "height": "26px", "borderRadius": "4px",
                    "border": f"1px solid {s.BORDER_STRONG}", "background": "oklch(0.22 0.014 255)",
                    "color": "oklch(0.72 0.01 255)", "cursor": "pointer", "fontSize": "13px",
                    "display": "flex", "alignItems": "center", "justifyContent": "center", "flexShrink": 0,
                },
            ),
            style={"display": "flex", "alignItems": "center", "gap": "10px", "padding": "18px 16px", "borderBottom": f"1px solid {s.BORDER}", "minHeight": "28px"},
        ),
        rx.el.div(
            rx.el.button(
                "+", on_click=DashboardState.new_chat, title="new chat",
                style={
                    "width": "36px", "height": "36px", "borderRadius": "50%",
                    "border": f"1px solid {s.ACCENT}", "background": "transparent", "color": s.ACCENT,
                    "fontSize": "18px", "fontWeight": 600, "cursor": "pointer",
                    "display": "flex", "alignItems": "center", "justifyContent": "center", "lineHeight": 1,
                },
            ),
            style={"padding": "12px"},
        ),
        rx.el.div(
            rx.foreach(DashboardState.chat_list, _chat_row),
            style={"flex": 1, "overflowY": "auto", "padding": "4px 10px 10px"},
        ),
        rx.cond(
            ~DashboardState.sidebar_collapsed,
            rx.el.div(
                "HOPE v0.9 · personal assistant",
                style={"padding": "12px 16px", "borderTop": f"1px solid {s.BORDER}", "fontFamily": s.FONT_MONO, "fontSize": "10px", "color": "oklch(0.45 0.012 255)"},
            ),
        ),
        style={
            "position": "absolute", "left": 0, "top": "12px", "bottom": "12px",
            "width": rx.cond(DashboardState.sidebar_collapsed, "64px", "260px"),
            "background": s.PANEL_BG, "border": f"1px solid {s.BORDER}",
            "borderRadius": "0 4px 4px 0", "display": "flex", "flexDirection": "column",
            "transition": "width 0.2s ease", "zIndex": 20, "overflow": "visible",
        },
    )

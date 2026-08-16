import reflex as rx

from dashboard import styles as s
from dashboard.components.primitives import pointer_div
from dashboard.state import DashboardState


def _terminal_header() -> rx.Component:
    return rx.el.div(
        pointer_div(
            rx.el.div(style={"width": "9px", "height": "9px", "borderRadius": "2px", "background": s.ACCENT}),
            rx.el.div(
                "HOPE // terminal",
                style={
                    "fontFamily": s.FONT_MONO, "fontSize": "10.5px", "letterSpacing": "1.5px",
                    "textTransform": "uppercase", "opacity": 0.55,
                },
            ),
            on_mouse_down=DashboardState.start_terminal_drag,
            style={"display": "flex", "alignItems": "center", "gap": "10px", "cursor": "grab", "flex": 1},
        ),
        rx.el.button(
            "×", on_click=DashboardState.close_terminal, title="close",
            style={
                "width": "22px", "height": "22px", "borderRadius": "6px", "border": f"1px solid {s.BORDER_STRONG}",
                "background": "oklch(0.22 0.014 255)", "color": "oklch(0.6 0.01 255)", "cursor": "pointer",
                "fontSize": "12px", "display": "flex", "alignItems": "center", "justifyContent": "center",
            },
        ),
        style={"display": "flex", "alignItems": "center", "gap": "10px", "padding": "12px 14px", "borderBottom": f"1px solid {s.BORDER_STRONG}", "flexShrink": 0},
    )


def _log_line(line: rx.Var[str]) -> rx.Component:
    return rx.el.div(line, style={"whiteSpace": "pre-wrap", "wordBreak": "break-word"})


def terminal_panel() -> rx.Component:
    return rx.cond(
        DashboardState.terminal_open,
        rx.el.div(
            rx.el.div(style=s.CORNER_BRACKET_TL),
            rx.el.div(style=s.CORNER_BRACKET_BR),
            rx.el.div(
                _terminal_header(),
                rx.auto_scroll(
                    rx.foreach(DashboardState.terminal_lines, _log_line),
                    style={
                        "flex": 1, "overflowY": "auto", "padding": "10px 14px",
                        "fontFamily": s.FONT_MONO, "fontSize": "11.5px", "lineHeight": 1.5,
                        "color": "oklch(0.75 0.01 255)",
                    },
                ),
                style={
                    "position": "absolute", "inset": 0, "borderRadius": "6px", "overflow": "hidden",
                    "display": "flex", "flexDirection": "column", "background": s.PANEL_HEADER_BG,
                },
            ),
            style={
                "position": "absolute",
                "left": f"{DashboardState.terminal_x}px", "top": f"{DashboardState.terminal_y}px",
                "width": "480px", "height": "220px",
                "background": "oklch(0.185 0.016 255 / 0.99)", "border": f"1px solid {s.BORDER_STRONG}",
                "borderRadius": "6px", "boxShadow": "0 14px 30px oklch(0.03 0 0 / 0.45)",
                "display": "flex", "flexDirection": "column", "zIndex": 25, "overflow": "visible",
            },
        ),
    )

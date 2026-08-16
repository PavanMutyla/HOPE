import reflex as rx

from dashboard import styles as s
from dashboard.components.primitives import pointer_div
from dashboard.data import ATTACH_TYPES, MODEL_OPTIONS
from dashboard.state import DashboardState

VOICE_BAR_HEIGHTS = [6, 14, 9, 13, 5]


def _dropdown_item(label: str, on_click) -> rx.Component:
    return rx.el.div(
        label,
        on_click=on_click,
        style={"padding": "8px 12px", "fontFamily": s.FONT_MONO, "fontSize": "11px", "color": "oklch(0.82 0.006 255)", "cursor": "pointer"},
    )


def _model_switcher() -> rx.Component:
    return rx.el.div(
        rx.el.button(
            rx.el.span(DashboardState.model),
            rx.el.span("▾", style={"fontSize": "8px"}),
            on_click=DashboardState.toggle_model_menu,
            style={
                "display": "flex", "alignItems": "center", "gap": "6px", "padding": "5px 9px",
                "borderRadius": "6px", "border": f"1px solid {s.BORDER_STRONG}", "background": "oklch(0.22 0.014 255)",
                "color": "oklch(0.7 0.01 255)", "fontFamily": s.FONT_MONO, "fontSize": "10.5px", "cursor": "pointer",
            },
        ),
        rx.cond(
            DashboardState.model_menu_open,
            rx.el.div(
                *[_dropdown_item(opt, DashboardState.select_model(opt)) for opt in MODEL_OPTIONS],
                style={
                    "position": "absolute", "right": 0, "top": "30px", "background": "oklch(0.22 0.016 255)",
                    "border": f"1px solid {s.BORDER_STRONG}", "borderRadius": "4px", "overflow": "hidden",
                    "zIndex": 40, "minWidth": "150px", "boxShadow": "0 10px 24px oklch(0.03 0 0 / 0.5)",
                },
            ),
        ),
        style={"position": "relative"},
    )


def _panel_header() -> rx.Component:
    return rx.el.div(
        pointer_div(
            rx.el.div(style={"width": "9px", "height": "9px", "borderRadius": "2px", "background": s.ACCENT}),
            rx.el.div("thread // active", style={"fontFamily": s.FONT_MONO, "fontSize": "10.5px", "letterSpacing": "1.5px", "textTransform": "uppercase", "opacity": 0.55}),
            on_mouse_down=DashboardState.start_panel_drag,
            style={"display": "flex", "alignItems": "center", "gap": "10px", "cursor": "grab", "flex": 1},
        ),
        rx.el.div(
            rx.el.button(
                "×", on_click=DashboardState.close_panel, title="close",
                style={
                    "width": "22px", "height": "22px", "borderRadius": "6px", "border": f"1px solid {s.BORDER_STRONG}",
                    "background": "oklch(0.22 0.014 255)", "color": "oklch(0.6 0.01 255)", "cursor": "pointer",
                    "fontSize": "12px", "display": "flex", "alignItems": "center", "justifyContent": "center",
                },
            ),
            _model_switcher(),
            style={"position": "relative", "marginLeft": "auto", "display": "flex", "alignItems": "center", "gap": "8px"},
        ),
        style={"display": "flex", "alignItems": "center", "gap": "10px", "padding": "12px 14px", "borderBottom": f"1px solid {s.BORDER_STRONG}", "flexShrink": 0},
    )


def _user_message(m: rx.Var[dict]) -> rx.Component:
    return rx.el.div(
        rx.cond(
            m["is_editing"],
            rx.fragment(
                rx.debounce_input(
                    rx.el.textarea(
                        value=m["edit_value"],
                        on_change=DashboardState.edit_change(m["id"]),
                        style={
                            "width": "260px", "minHeight": "50px", "background": "oklch(0.24 0.02 255)",
                            "border": "1px solid oklch(0.4 0.03 255)", "borderRadius": "8px", "padding": "8px 10px",
                            "color": "oklch(0.9 0.006 255)", "fontSize": "12.5px", "fontFamily": s.FONT_SANS,
                        },
                    ),
                    debounce_timeout=200,
                ),
                rx.el.div(
                    rx.el.button(
                        "save", on_click=DashboardState.save_edit(DashboardState.active_chat_id, m["id"]),
                        style={
                            "fontSize": "10.5px", "fontFamily": s.FONT_MONO, "padding": "4px 9px", "borderRadius": "6px",
                            "border": f"1px solid {s.ACCENT}", "background": "oklch(0.24 0.05 200 / 0.3)", "color": s.ACCENT, "cursor": "pointer",
                        },
                    ),
                    rx.el.button(
                        "cancel", on_click=DashboardState.cancel_edit,
                        style={
                            "fontSize": "10.5px", "fontFamily": s.FONT_MONO, "padding": "4px 9px", "borderRadius": "6px",
                            "border": "1px solid oklch(0.4 0.02 255)", "background": "transparent", "color": s.TEXT_DIM, "cursor": "pointer",
                        },
                    ),
                    style={"display": "flex", "gap": "6px"},
                ),
            ),
            rx.fragment(
                rx.el.div(
                    m["text"],
                    style={
                        "background": "oklch(0.26 0.03 200 / 0.55)", "border": "1px solid oklch(0.42 0.04 200 / 0.6)",
                        "borderRadius": "8px 8px 2px 8px", "padding": "9px 12px", "fontSize": "13px", "lineHeight": 1.5,
                        "color": "oklch(0.94 0.006 255)",
                    },
                ),
                rx.el.div(
                    rx.el.button("edit", on_click=DashboardState.start_edit(m["id"], m["text"]), style=s.GHOST_BUTTON),
                    rx.el.button("copy", on_click=DashboardState.copy_text(m["text"]), style=s.GHOST_BUTTON),
                    style={"display": "flex", "gap": "8px"},
                ),
            ),
        ),
        style={"alignSelf": "flex-end", "maxWidth": "82%", "display": "flex", "flexDirection": "column", "alignItems": "flex-end", "gap": "4px"},
    )


def _assistant_message(m: rx.Var[dict]) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            m["avatar_initial"],
            style={
                "width": "26px", "height": "26px", "borderRadius": "50%", "background": m["avatar_color"],
                "color": "oklch(0.15 0 0)", "fontFamily": s.FONT_MONO, "fontSize": "11px", "fontWeight": 700,
                "display": "flex", "alignItems": "center", "justifyContent": "center", "flexShrink": 0, "marginTop": "2px",
            },
        ),
        rx.el.div(
            rx.el.div(m["agent_name"], style={"fontFamily": s.FONT_MONO, "fontSize": "10px", "color": m["avatar_color"], "fontWeight": 600}),
            rx.el.div(
                m["text"],
                style={
                    "background": "oklch(0.24 0.014 255)", "border": f"1px solid {s.BORDER}",
                    "borderRadius": "8px 8px 8px 2px", "padding": "10px 12px", "fontSize": "13px",
                    "lineHeight": 1.55, "color": "oklch(0.88 0.006 255)",
                },
            ),
            rx.el.div(
                rx.el.button("copy", on_click=DashboardState.copy_text(m["text"]), style=s.GHOST_BUTTON),
                rx.el.button("regenerate", on_click=DashboardState.regenerate(DashboardState.active_chat_id, m["id"]), style=s.GHOST_BUTTON),
                rx.cond(
                    m["has_versions"],
                    rx.el.div(
                        rx.el.button("‹", on_click=DashboardState.switch_version(DashboardState.active_chat_id, m["id"], -1), style={"background": "none", "border": "none", "color": "inherit", "cursor": "pointer", "fontSize": "11px"}),
                        rx.el.span(m["version_label"]),
                        rx.el.button("›", on_click=DashboardState.switch_version(DashboardState.active_chat_id, m["id"], 1), style={"background": "none", "border": "none", "color": "inherit", "cursor": "pointer", "fontSize": "11px"}),
                        style={"display": "flex", "alignItems": "center", "gap": "5px", "marginLeft": "auto", "fontFamily": s.FONT_MONO, "fontSize": "10px", "color": "oklch(0.55 0.012 255)"},
                    ),
                ),
                style={"display": "flex", "alignItems": "center", "gap": "10px"},
            ),
            style={"display": "flex", "flexDirection": "column", "gap": "5px", "minWidth": 0},
        ),
        style={"alignSelf": "flex-start", "maxWidth": "86%", "display": "flex", "gap": "8px"},
    )


def _message_row(m: rx.Var[dict]) -> rx.Component:
    return rx.cond(m["is_user"], _user_message(m), _assistant_message(m))


def _thinking_dots() -> rx.Component:
    return rx.cond(
        DashboardState.is_thinking,
        rx.el.div(
            *[
                rx.el.div(style={"width": "6px", "height": "6px", "borderRadius": "50%", "background": s.ACCENT, "animation": f"hope-blink 1s ease-in-out infinite {i * 0.15}s"})
                for i in range(3)
            ],
            style={"alignSelf": "flex-start", "display": "flex", "gap": "4px", "padding": "10px 12px"},
        ),
    )


def _attachments_row() -> rx.Component:
    return rx.cond(
        DashboardState.attachments.length() > 0,
        rx.el.div(
            rx.foreach(
                DashboardState.attachments,
                lambda att: rx.el.div(
                    rx.el.span(f"{att['type']}: {att['name']}"),
                    rx.el.button("×", on_click=DashboardState.remove_attachment(att["id"]), style={"background": "none", "border": "none", "color": "oklch(0.5 0.01 255)", "cursor": "pointer", "fontSize": "11px"}),
                    style={
                        "display": "flex", "alignItems": "center", "gap": "6px", "padding": "4px 9px", "borderRadius": "4px",
                        "background": "oklch(0.24 0.02 255)", "border": f"1px solid {s.BORDER_STRONG}",
                        "fontFamily": s.FONT_MONO, "fontSize": "10.5px", "color": "oklch(0.7 0.01 255)",
                    },
                ),
            ),
            style={"display": "flex", "gap": "6px", "flexWrap": "wrap", "padding": "0 14px"},
        ),
    )


def _attach_menu() -> rx.Component:
    return rx.el.div(
        rx.el.button(
            rx.el.svg(
                rx.el.path(d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"),
                width="16", height="16", view_box="0 0 24 24", fill="none", stroke="currentColor",
                stroke_width="2", stroke_linecap="round", stroke_linejoin="round",
            ),
            on_click=DashboardState.toggle_attach_menu, title="attach",
            style={
                "width": "32px", "height": "32px", "borderRadius": "4px", "border": f"1px solid {s.BORDER_STRONG}",
                "background": "oklch(0.22 0.014 255)", "color": "oklch(0.65 0.01 255)", "cursor": "pointer",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
            },
        ),
        rx.cond(
            DashboardState.attach_menu_open,
            rx.el.div(
                *[_dropdown_item(t, DashboardState.add_attachment(t)) for t in ATTACH_TYPES],
                style={
                    "position": "absolute", "left": 0, "bottom": "38px", "background": "oklch(0.22 0.016 255)",
                    "border": f"1px solid {s.BORDER_STRONG}", "borderRadius": "4px", "overflow": "hidden",
                    "zIndex": 40, "minWidth": "140px", "boxShadow": "0 10px 24px oklch(0.03 0 0 / 0.5)",
                },
            ),
        ),
        style={"position": "relative", "flexShrink": 0},
    )


def _voice_toggle() -> rx.Component:
    return rx.el.button(
        rx.el.div(
            *[
                rx.el.div(style={
                    "width": "2.5px", "background": "currentColor", "borderRadius": "2px",
                    "height": f"{h}px",
                    "animation": rx.cond(DashboardState.listening, f"hope-wave 0.9s ease-in-out infinite {i * 0.15}s", "none"),
                })
                for i, h in enumerate(VOICE_BAR_HEIGHTS)
            ],
            style={"display": "flex", "alignItems": "center", "gap": "2.5px", "height": "14px"},
        ),
        on_click=DashboardState.toggle_voice, title="voice",
        style={
            "width": "32px", "height": "32px", "borderRadius": "4px",
            "border": rx.cond(DashboardState.listening, "1px solid oklch(0.78 0.15 25)", f"1px solid {s.BORDER_STRONG}"),
            "background": rx.cond(DashboardState.listening, "oklch(0.35 0.08 25 / 0.4)", "oklch(0.22 0.014 255)"),
            "color": rx.cond(DashboardState.listening, "oklch(0.8 0.15 25)", "oklch(0.65 0.01 255)"),
            "cursor": "pointer", "flexShrink": 0, "display": "flex", "alignItems": "center", "justifyContent": "center",
        },
    )


def _compose_bar() -> rx.Component:
    return rx.el.div(
        _attach_menu(),
        _voice_toggle(),
        rx.debounce_input(
            rx.el.textarea(
                value=DashboardState.compose_text,
                on_change=DashboardState.set_compose_text,
                on_key_down=DashboardState.on_compose_key_down,
                placeholder="Message HOPE…",
                style={
                    "flex": 1, "minHeight": "32px", "maxHeight": "100px", "resize": "none",
                    "background": "oklch(0.22 0.014 255)", "border": f"1px solid {s.BORDER_STRONG}", "borderRadius": "4px",
                    "padding": "8px 10px", "color": "oklch(0.9 0.006 255)", "fontSize": "13px",
                    "fontFamily": s.FONT_SANS, "outline": "none",
                },
            ),
            debounce_timeout=200,
            force_notify_by_enter=True,
        ),
        rx.el.button(
            "↑", on_click=DashboardState.send_message,
            style={
                "width": "32px", "height": "32px", "borderRadius": "4px", "border": f"1px solid {s.ACCENT}",
                "background": "oklch(0.78 0.14 200 / 0.15)", "color": "oklch(0.85 0.1 200)", "cursor": "pointer",
                "flexShrink": 0, "fontSize": "15px", "display": "flex", "alignItems": "center", "justifyContent": "center",
            },
        ),
        style={"display": "flex", "alignItems": "flex-end", "gap": "8px", "padding": "12px 14px", "borderTop": f"1px solid {s.BORDER}", "flexShrink": 0},
    )


def chat_panel() -> rx.Component:
    return rx.cond(
        DashboardState.panel_open,
        rx.el.div(
            rx.el.div(style=s.CORNER_BRACKET_TL),
            rx.el.div(style=s.CORNER_BRACKET_BR),
            rx.el.div(
                _panel_header(),
                rx.el.div(
                    rx.foreach(DashboardState.display_messages, _message_row),
                    _thinking_dots(),
                    style={"flex": 1, "overflowY": "auto", "padding": "14px", "display": "flex", "flexDirection": "column", "gap": "14px"},
                ),
                _attachments_row(),
                _compose_bar(),
                style={
                    "position": "absolute", "inset": 0, "borderRadius": "6px", "overflow": "hidden",
                    "display": "flex", "flexDirection": "column", "background": s.PANEL_HEADER_BG,
                },
            ),
            style={
                "position": "absolute",
                "left": f"{DashboardState.panel_x}px", "top": f"{DashboardState.panel_y}px",
                "width": "420px", "height": "600px",
                "background": "oklch(0.185 0.016 255 / 0.99)", "border": f"1px solid {s.BORDER_STRONG}",
                "borderRadius": "6px", "boxShadow": "0 14px 30px oklch(0.03 0 0 / 0.45)",
                "display": "flex", "flexDirection": "column", "zIndex": 30, "overflow": "visible",
            },
        ),
    )

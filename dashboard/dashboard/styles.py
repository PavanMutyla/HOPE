"""Shared style tokens, ported from the Claude Design prototype's inline
oklch palette and font stack."""

ACCENT = "oklch(0.78 0.14 200)"
BG = "oklch(0.16 0.012 255)"
CANVAS_BG = "oklch(0.155 0.012 255)"
PANEL_BG = "oklch(0.185 0.014 255)"
PANEL_HEADER_BG = "oklch(0.185 0.016 255)"
BORDER = "oklch(0.3 0.02 255)"
BORDER_STRONG = "oklch(0.34 0.02 255)"
TEXT = "oklch(0.93 0.006 255)"
TEXT_DIM = "oklch(0.6 0.01 255)"
TEXT_DIMMER = "oklch(0.5 0.012 255)"
INK = "#3a3226"

FONT_SANS = "'IBM Plex Sans', sans-serif"
FONT_MONO = "'IBM Plex Mono', monospace"
FONT_HAND = "'Caveat', cursive"

CORNER_BRACKET_TL = {
    "position": "absolute", "top": "-1px", "left": "-1px",
    "width": "12px", "height": "12px",
    "borderTop": f"2px solid {ACCENT}", "borderLeft": f"2px solid {ACCENT}",
    "opacity": 0.7,
}
CORNER_BRACKET_TR = {
    "position": "absolute", "top": "-1px", "right": "-1px",
    "width": "12px", "height": "12px",
    "borderTop": f"2px solid {ACCENT}", "borderRight": f"2px solid {ACCENT}",
    "opacity": 0.7,
}
CORNER_BRACKET_BL = {
    "position": "absolute", "bottom": "-1px", "left": "-1px",
    "width": "12px", "height": "12px",
    "borderBottom": f"2px solid {ACCENT}", "borderLeft": f"2px solid {ACCENT}",
    "opacity": 0.7,
}
CORNER_BRACKET_BR = {
    "position": "absolute", "bottom": "-1px", "right": "-1px",
    "width": "12px", "height": "12px",
    "borderBottom": f"2px solid {ACCENT}", "borderRight": f"2px solid {ACCENT}",
    "opacity": 0.7,
}

GHOST_BUTTON = {
    "fontSize": "10px", "fontFamily": FONT_MONO, "background": "none",
    "border": "none", "color": TEXT_DIMMER, "cursor": "pointer", "padding": "0",
}

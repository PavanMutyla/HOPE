"""Shared style tokens.

Descended from the Claude Design prototype's oklch palette, with the text
ramp rebuilt: the prototype's dimmest two tiers measured 3.1:1 and 2.5:1
against the panel ground and were carrying thread previews and timestamps at
9.5px, which is below WCAG AA for body text. Every tier below now clears 4.5:1
on both grounds, and hierarchy is carried by size and weight as well as value.

One accent, locked to the whole product. LIVE is the single exception and is
strictly semantic: it means the voice pipeline is actually running. Nothing
decorative is ever green.
"""

# ── ground ──────────────────────────────────────────────────────
BG = "oklch(0.16 0.012 255)"            # the desk
CANVAS_BG = "oklch(0.155 0.012 255)"    # corkboard surface, a shade deeper
PANEL_BG = "oklch(0.185 0.014 255)"
PANEL_RAISED = "oklch(0.215 0.015 255)"  # rows, inputs, anything sitting on a panel

BORDER = "oklch(0.30 0.02 255)"
BORDER_STRONG = "oklch(0.38 0.02 255)"

# ── text ramp (all ≥ 4.5:1 on BG and PANEL_BG) ──────────────────
TEXT = "oklch(0.93 0.006 255)"          # 15.2:1 — primary
TEXT_DIM = "oklch(0.72 0.010 255)"      #  7.5:1 — secondary
TEXT_MUTED = "oklch(0.60 0.012 255)"    #  4.7:1 — tertiary, the floor

# ── accent ──────────────────────────────────────────────────────
ACCENT = "oklch(0.78 0.14 200)"         #  9.9:1 — the one accent
ACCENT_SOFT = "oklch(0.78 0.14 200 / 0.12)"
LIVE = "oklch(0.80 0.16 145)"           # 10.6:1 — pipeline is running, nothing else
LIVE_SOFT = "oklch(0.80 0.16 145 / 0.14)"

# ── paper (sticky notes keep the prototype's palette) ───────────
INK = "#3a3226"                         # 11.3:1 on the lightest paper

# ── type ────────────────────────────────────────────────────────
FONT_SANS = "'IBM Plex Sans', ui-sans-serif, system-ui, sans-serif"
FONT_MONO = "'IBM Plex Mono', ui-monospace, SFMono-Regular, monospace"
FONT_HAND = "'Caveat', ui-rounded, cursive"

# 11px is the floor. The prototype went to 9px, which is unreadable at arm's
# length on a desk monitor and was where the contrast failures clustered.
SIZE_MICRO = "11px"
SIZE_META = "12px"
SIZE_BODY = "13.5px"
SIZE_TITLE = "15px"

RADIUS = "5px"      # one radius for panels, rows and buttons
RADIUS_PILL = "999px"

# ── shared fragments ────────────────────────────────────────────

def corner_bracket(vertical: str, horizontal: str, color: str = ACCENT) -> dict:
    """HUD corner tick. The prototype hard-coded four near-identical dicts;
    they only ever varied by which two edges get a border."""
    return {
        "position": "absolute", vertical: "-1px", horizontal: "-1px",
        "width": "12px", "height": "12px",
        f"border{vertical.capitalize()}": f"2px solid {color}",
        f"border{horizontal.capitalize()}": f"2px solid {color}",
        "opacity": 0.7, "pointerEvents": "none",
    }


# Visible keyboard focus everywhere. The prototype had none at all: every
# control was a div or an unstyled button, so tabbing through it was invisible.
FOCUS_RING = {
    "outline": f"2px solid {ACCENT}",
    "outlineOffset": "2px",
}

GHOST_BUTTON = {
    "fontSize": SIZE_MICRO, "fontFamily": FONT_MONO, "background": "none",
    "border": "none", "color": TEXT_MUTED, "cursor": "pointer",
    "padding": "4px 6px", "borderRadius": RADIUS,
}

PANEL = {
    "background": PANEL_BG,
    "border": f"1px solid {BORDER}",
    "borderRadius": RADIUS,
}

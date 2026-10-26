"""Drag primitive: rx.el.div's default on_mouse_* triggers carry no event
data (no_args_event_spec) — dragging needs client_x/client_y deltas, so this
subclass swaps in pointer_event_spec for the mouse triggers we drag with.
"""

from reflex.event import pointer_event_spec, EventHandler
from reflex_components_core.el.elements.typography import Div as _Div


class PointerDiv(_Div):
    on_mouse_down: EventHandler[pointer_event_spec]
    on_mouse_move: EventHandler[pointer_event_spec]
    on_mouse_up: EventHandler[pointer_event_spec]


pointer_div = PointerDiv.create

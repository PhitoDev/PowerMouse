from __future__ import annotations

import mouse as _mouse

from powermouse.domain.controllers.mouse import MouseController
from powermouse.domain.models.mouse import MouseEvent, MouseEventType


class SystemMouseController(MouseController):
    """MouseController that dispatches events to the OS cursor via the mouse library."""

    def handle_event(self, mouse: MouseEvent) -> None:
        button = str(mouse.button)
        match mouse.event_type:
            case MouseEventType.MOVE:
                _mouse.move(mouse.x, mouse.y, absolute=True, duration=0)
            case MouseEventType.BUTTON_DOWN:
                _mouse.press(button=button)
            case MouseEventType.BUTTON_UP:
                _mouse.release(button=button)
            case _:
                raise ValueError(f"Unsupported mouse event type: {mouse.event_type!r}")

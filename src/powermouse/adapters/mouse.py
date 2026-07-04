from __future__ import annotations

from pynput.mouse import Controller, Button

from powermouse.domain.controllers.mouse import MouseController
from powermouse.domain.models.mouse import MouseEvent, MouseEventType


class SystemMouseController(MouseController):
    """MouseController that dispatches events to the OS cursor via pynput."""

    def __init__(self):
        self._mouse = Controller()

        # Map your domain button enums/strings to pynput Buttons
        self._button_map = {
            "left": Button.left,
            "right": Button.right,
            "middle": Button.middle
        }

    def _get_pynput_button(self, button_enum) -> Button:
        # Extracts the raw string (e.g., "left") regardless of how the enum is formatted
        btn_str = str(button_enum).lower().split('.')[-1]
        return self._button_map.get(btn_str, Button.left)

    def handle_event(self, mouse_event: MouseEvent) -> None:
        match mouse_event.event_type:
            case MouseEventType.MOVE:
                # pynput handles absolute positioning instantly
                self._mouse.position = (mouse_event.x, mouse_event.y)

            case MouseEventType.BUTTON_DOWN:
                btn = self._get_pynput_button(mouse_event.button)
                self._mouse.press(btn)

            case MouseEventType.BUTTON_UP:
                btn = self._get_pynput_button(mouse_event.button)
                self._mouse.release(btn)

            case _:
                raise ValueError(f"Unsupported mouse event type: {mouse_event.event_type!r}")

"""Pure-logic translator mapping GestureEvents to MouseEvent sequences.

Lives in usecases (not adapters) because it has no external dependencies;
just enum-to-enum policy that needs state for the toggle-hold gestures.
"""
from __future__ import annotations

from typing import List

from powermouse.domain.models.gesture import GestureEvent
from powermouse.domain.models.mouse import ClickInterface, MouseButton, MouseEvent
from powermouse.domain.usecases.mouse_actions import MouseActionCoordinator


GESTURE_CLICK_CHEAT_SHEET = [
    ("Wink left eye", "Left click"),
    ("Wink right eye", "Right click"),
    ("Squint left eye", "Double click"),
    ("Squint right eye", "Toggle hold right click (drag)"),
    ("Raise eyebrows", "Middle click"),
    ("Open jaw", "Toggle hold left click (drag)"),
]


class GestureToMouseTranslator:
    """Map GestureEvents to MouseEvent sequences per docs/architecture.md §4.2
    and requirements §4 (Gesture Clicking)."""

    def __init__(self, coordinator: MouseActionCoordinator | None = None) -> None:
        self.coordinator = coordinator or MouseActionCoordinator()

    def translate(self, gesture: GestureEvent, cursor: tuple[int, int]) -> List[MouseEvent]:
        match gesture:
            case GestureEvent.LEFT_BLINK:
                return self.coordinator.click(MouseButton.LEFT, cursor)
            case GestureEvent.RIGHT_BLINK:
                return self.coordinator.click(MouseButton.RIGHT, cursor)
            case GestureEvent.LEFT_SQUINT:
                return self.coordinator.click(MouseButton.LEFT, cursor, 2)
            case GestureEvent.RAISED_EYEBROWS:
                return self.coordinator.click(MouseButton.MIDDLE, cursor)
            case GestureEvent.OPEN_MOUTH:
                if self.coordinator.is_owned(ClickInterface.GESTURE, MouseButton.LEFT):
                    return self.coordinator.release(ClickInterface.GESTURE, MouseButton.LEFT, cursor)
                return self.coordinator.acquire(ClickInterface.GESTURE, MouseButton.LEFT, cursor)
            case GestureEvent.RIGHT_SQUINT:
                if self.coordinator.is_owned(ClickInterface.GESTURE, MouseButton.RIGHT):
                    return self.coordinator.release(ClickInterface.GESTURE, MouseButton.RIGHT, cursor)
                return self.coordinator.acquire(ClickInterface.GESTURE, MouseButton.RIGHT, cursor)
            case _:
                return []

    def reset_holds(self, cursor: tuple[int, int]) -> List[MouseEvent]:
        """Return events that release any active holds. Call when tracking stops."""
        return self.coordinator.release_all(ClickInterface.GESTURE, cursor)

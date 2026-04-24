"""Pure-logic translator mapping GestureEvents to MouseEvent sequences.

Lives in usecases (not adapters) because it has no external dependencies;
just enum-to-enum policy that needs state for the toggle-hold gestures.
"""
from __future__ import annotations

from typing import List

from powermouse.domain.models.gesture import GestureEvent
from powermouse.domain.models.mouse import MouseButton, MouseEvent, MouseEventType


def _click(button: MouseButton, x: int = 0, y: int = 0) -> List[MouseEvent]:
    """Produce a full press+release pair at the given position."""
    return [
        MouseEvent(button=button, x=x, y=y, event_type=MouseEventType.BUTTON_DOWN),
        MouseEvent(button=button, x=x, y=y, event_type=MouseEventType.BUTTON_UP),
    ]


class GestureToMouseTranslator:
    """Map GestureEvents to MouseEvent sequences per docs/architecture.md §4.2
    and requirements §4 (Gesture Clicking)."""

    def __init__(self) -> None:
        self._left_hold_active: bool = False
        self._right_hold_active: bool = False

    def translate(self, gesture: GestureEvent, cursor: tuple[int, int]) -> List[MouseEvent]:
        x, y = cursor
        match gesture:
            case GestureEvent.LEFT_BLINK:
                return _click(MouseButton.LEFT, x, y)
            case GestureEvent.RIGHT_BLINK:
                return _click(MouseButton.RIGHT, x, y)
            case GestureEvent.LEFT_SQUINT:
                # Double click: two press/release pairs.
                return _click(MouseButton.LEFT, x, y) + _click(MouseButton.LEFT, x, y)
            case GestureEvent.RAISED_EYEBROWS:
                return _click(MouseButton.MIDDLE, x, y)
            case GestureEvent.OPEN_MOUTH:
                # Toggle holding left click.
                self._left_hold_active = not self._left_hold_active
                event_type = (
                    MouseEventType.BUTTON_DOWN
                    if self._left_hold_active
                    else MouseEventType.BUTTON_UP
                )
                return [MouseEvent(button=MouseButton.LEFT, x=x, y=y, event_type=event_type)]
            case GestureEvent.RIGHT_SQUINT:
                # Toggle holding right click.
                self._right_hold_active = not self._right_hold_active
                event_type = (
                    MouseEventType.BUTTON_DOWN
                    if self._right_hold_active
                    else MouseEventType.BUTTON_UP
                )
                return [MouseEvent(button=MouseButton.RIGHT, x=x, y=y, event_type=event_type)]
            case _:
                return []

    def reset_holds(self, cursor: tuple[int, int]) -> List[MouseEvent]:
        """Return events that release any active holds. Call when tracking stops."""
        x, y = cursor
        events: List[MouseEvent] = []
        if self._left_hold_active:
            self._left_hold_active = False
            events.append(
                MouseEvent(button=MouseButton.LEFT, x=x, y=y, event_type=MouseEventType.BUTTON_UP)
            )
        if self._right_hold_active:
            self._right_hold_active = False
            events.append(
                MouseEvent(button=MouseButton.RIGHT, x=x, y=y, event_type=MouseEventType.BUTTON_UP)
            )
        return events

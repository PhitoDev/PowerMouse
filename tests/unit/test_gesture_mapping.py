"""Unit tests for ``powermouse.domain.usecases.gesture_mapping``."""
from __future__ import annotations

from powermouse.domain.models.gesture import GestureEvent
from powermouse.domain.models.mouse import MouseButton, MouseEventType
from powermouse.domain.usecases.gesture_mapping import GestureToMouseTranslator


def _types(events):
    return [(e.button, e.event_type) for e in events]


class TestGestureToMouseTranslator:
    def test_left_blink_emits_left_click(self):
        t = GestureToMouseTranslator()
        events = t.translate(GestureEvent.LEFT_BLINK, (3, 4))
        assert _types(events) == [
            (MouseButton.LEFT, MouseEventType.BUTTON_DOWN),
            (MouseButton.LEFT, MouseEventType.BUTTON_UP),
        ]
        assert all(e.x == 3 and e.y == 4 for e in events)

    def test_right_blink_emits_right_click(self):
        t = GestureToMouseTranslator()
        events = t.translate(GestureEvent.RIGHT_BLINK, (0, 0))
        assert _types(events) == [
            (MouseButton.RIGHT, MouseEventType.BUTTON_DOWN),
            (MouseButton.RIGHT, MouseEventType.BUTTON_UP),
        ]

    def test_left_squint_emits_double_click(self):
        t = GestureToMouseTranslator()
        events = t.translate(GestureEvent.LEFT_SQUINT, (0, 0))
        assert _types(events) == [
            (MouseButton.LEFT, MouseEventType.BUTTON_DOWN),
            (MouseButton.LEFT, MouseEventType.BUTTON_UP),
            (MouseButton.LEFT, MouseEventType.BUTTON_DOWN),
            (MouseButton.LEFT, MouseEventType.BUTTON_UP),
        ]

    def test_raised_eyebrows_emits_middle_click(self):
        t = GestureToMouseTranslator()
        events = t.translate(GestureEvent.RAISED_EYEBROWS, (0, 0))
        assert _types(events) == [
            (MouseButton.MIDDLE, MouseEventType.BUTTON_DOWN),
            (MouseButton.MIDDLE, MouseEventType.BUTTON_UP),
        ]

    def test_open_mouth_toggles_left_hold(self):
        t = GestureToMouseTranslator()
        first = t.translate(GestureEvent.OPEN_MOUTH, (1, 1))
        second = t.translate(GestureEvent.OPEN_MOUTH, (1, 1))
        assert _types(first) == [(MouseButton.LEFT, MouseEventType.BUTTON_DOWN)]
        assert _types(second) == [(MouseButton.LEFT, MouseEventType.BUTTON_UP)]

    def test_right_squint_toggles_right_hold(self):
        t = GestureToMouseTranslator()
        first = t.translate(GestureEvent.RIGHT_SQUINT, (1, 1))
        second = t.translate(GestureEvent.RIGHT_SQUINT, (1, 1))
        assert _types(first) == [(MouseButton.RIGHT, MouseEventType.BUTTON_DOWN)]
        assert _types(second) == [(MouseButton.RIGHT, MouseEventType.BUTTON_UP)]

    def test_reset_holds_releases_active_holds_only(self):
        t = GestureToMouseTranslator()
        # Engage both holds.
        t.translate(GestureEvent.OPEN_MOUTH, (0, 0))
        t.translate(GestureEvent.RIGHT_SQUINT, (0, 0))
        events = t.reset_holds((5, 6))
        assert _types(events) == [
            (MouseButton.LEFT, MouseEventType.BUTTON_UP),
            (MouseButton.RIGHT, MouseEventType.BUTTON_UP),
        ]
        # Cursor coordinates from reset_holds must match.
        assert all(e.x == 5 and e.y == 6 for e in events)
        # Calling reset_holds again with no active holds must produce nothing.
        assert t.reset_holds((0, 0)) == []

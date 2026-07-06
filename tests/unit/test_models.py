"""Unit tests for ``powermouse.domain.models``."""
from __future__ import annotations

import numpy as np
import pytest

from powermouse.domain.models.camera import Camera, FaceTrackerSettings
from powermouse.domain.models.gesture import GestureEvent, GestureEventListener
from powermouse.domain.models.mouse import (
    ClickInterface,
    MouseButton,
    MouseEvent,
    MouseEventListener,
    MouseEventType,
)
from powermouse.domain.models.profile import Profile


class TestCamera:
    def test_update_frame_replaces_frame_and_dimensions(self, camera: Camera):
        new_frame = np.zeros((100, 200, 3), dtype=np.uint8)
        camera.update_frame(new_frame)
        assert camera.current_frame is new_frame
        assert camera.frame_width == 200
        assert camera.frame_height == 100


class TestFaceTrackerSettings:
    def test_defaults(self, face_tracker_settings: FaceTrackerSettings):
        assert face_tracker_settings.speed == 3.0
        assert face_tracker_settings.acceleration == 3.0
        assert face_tracker_settings.sensitivity == (1.0, 1.0)
        assert face_tracker_settings.smoothness == 0.5
        assert face_tracker_settings.deadzone_radius_px == 5
        assert face_tracker_settings.active_area_x == (0.0, 1.0)
        assert face_tracker_settings.active_area_y == (0.0, 1.0)
        assert face_tracker_settings.click_threshold_high == 0.6
        assert face_tracker_settings.click_threshold_low == 0.4

    def test_update_mutates_attributes(self, face_tracker_settings: FaceTrackerSettings):
        face_tracker_settings.update(speed=2.0, sensitivity=(2.0, 0.5))
        assert face_tracker_settings.speed == 2.0
        assert face_tracker_settings.sensitivity == (2.0, 0.5)

    def test_update_unknown_attribute_is_set(self, face_tracker_settings: FaceTrackerSettings):
        # Documents current behaviour: ``update`` uses ``setattr`` blindly.
        face_tracker_settings.update(extra="value")
        assert getattr(face_tracker_settings, "extra") == "value"


class TestProfile:
    def test_set_active_toggle(self, sample_profile: Profile):
        sample_profile.set_active(False)
        assert sample_profile.is_active is False
        sample_profile.set_active(True)
        assert sample_profile.is_active is True

    def test_toggle_click_interface_records_state(self, sample_profile: Profile):
        sample_profile.toggle_click_interface(ClickInterface.DWELL, True)
        assert sample_profile.is_click_interface_enabled(ClickInterface.DWELL) is True

        sample_profile.toggle_click_interface(ClickInterface.DWELL, False)
        assert sample_profile.is_click_interface_enabled(ClickInterface.DWELL) is False

    def test_is_click_interface_defaults_false(self, sample_profile: Profile):
        assert sample_profile.is_click_interface_enabled(ClickInterface.VOICE) is False


class TestMouseModels:
    def test_mouse_button_str(self):
        assert str(MouseButton.LEFT) == "left"
        assert str(MouseButton.RIGHT) == "right"
        assert str(MouseButton.MIDDLE) == "middle"

    def test_mouse_event_str_includes_button_and_position(self):
        event = MouseEvent(MouseButton.RIGHT, 10, 20, MouseEventType.MOVE)
        assert "right" in str(event)
        assert "(10, 20)" in str(event)

    def test_mouse_event_listener_invokes_callback(self):
        received: list[MouseEvent] = []
        listener = MouseEventListener(callback=received.append)
        evt = MouseEvent(MouseButton.LEFT, 1, 2, MouseEventType.BUTTON_DOWN)
        listener.on_event(evt)
        assert received == [evt]


class TestGestureModels:
    def test_gesture_event_listener_invokes_callback(self):
        received: list[GestureEvent] = []
        listener = GestureEventListener(callback=received.append)
        listener.on_event(GestureEvent.LEFT_BLINK)
        assert received == [GestureEvent.LEFT_BLINK]

    @pytest.mark.parametrize(
        "event,value",
        [
            (GestureEvent.LEFT_BLINK, "left_blink"),
            (GestureEvent.RIGHT_BLINK, "right_blink"),
            (GestureEvent.LEFT_SQUINT, "left_squint"),
            (GestureEvent.RIGHT_SQUINT, "right_squint"),
            (GestureEvent.RAISED_EYEBROWS, "raised_eyebrows"),
            (GestureEvent.OPEN_MOUTH, "open_mouth"),
        ],
    )
    def test_gesture_event_values(self, event: GestureEvent, value: str):
        assert event.value == value

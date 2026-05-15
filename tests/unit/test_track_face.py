"""Unit tests for ``powermouse.domain.usecases.track_face``."""
from __future__ import annotations

from typing import List

import pytest

from powermouse.domain.models.gesture import GestureEvent
from powermouse.domain.models.mouse import MouseButton, MouseEvent, MouseEventType
from powermouse.domain.usecases import track_face
from powermouse.domain.usecases.gesture_mapping import GestureToMouseTranslator


@pytest.fixture
def sync_dispatch(monkeypatch):
    """Replace ``track_face._dispatch`` with a synchronous call so tests can
    assert on the recording mouse controller without sleeping for threads."""

    def _direct(controller, event):
        controller.handle_event(event)

    monkeypatch.setattr(track_face, "_dispatch", _direct)
    return _direct


class TestTrackingStep:
    def test_emits_move_event_each_frame(
        self,
        sync_dispatch,
        fake_camera_controller,
        fake_inference_controller,
        recording_mouse_controller,
    ):
        translator = GestureToMouseTranslator()
        captured_frames: List = []

        def frame_processor(frame, ts):
            captured_frames.append((frame, ts))

        track_face.tracking_step(
            camera_controller=fake_camera_controller,
            inference_controller=fake_inference_controller,
            mouse_controller=recording_mouse_controller,
            gesture_translator=translator,
            frame_processor=frame_processor,
        )

        # The camera should have been advanced.
        assert fake_camera_controller.update_calls == 1
        # The inference controller should have been handed the frame.
        assert len(fake_inference_controller.process_calls) == 1
        # Exactly one MOVE event should have been dispatched.
        moves = [
            e for e in recording_mouse_controller.events if e.event_type is MouseEventType.MOVE
        ]
        assert len(moves) == 1
        assert (moves[0].x, moves[0].y) == fake_inference_controller.get_cursor_position()
        # Frame processor must observe the same frame the camera produced.
        assert captured_frames and captured_frames[0][0] is fake_camera_controller.camera.current_frame

    def test_drains_all_pending_gestures(
        self,
        sync_dispatch,
        fake_camera_controller,
        recording_mouse_controller,
    ):
        from tests.conftest import FakeInferenceController

        inference = FakeInferenceController(
            cursor=(7, 9),
            gestures=[GestureEvent.LEFT_BLINK, GestureEvent.RIGHT_BLINK],
        )
        translator = GestureToMouseTranslator()

        track_face.tracking_step(
            camera_controller=fake_camera_controller,
            inference_controller=inference,
            mouse_controller=recording_mouse_controller,
            gesture_translator=translator,
            frame_processor=lambda *_: None,
        )

        events = recording_mouse_controller.events
        # 1 MOVE + 2 click pairs = 5 events.
        assert len(events) == 5
        assert events[0].event_type is MouseEventType.MOVE
        # First click pair: left.
        assert events[1].button is MouseButton.LEFT
        assert events[1].event_type is MouseEventType.BUTTON_DOWN
        assert events[2].event_type is MouseEventType.BUTTON_UP
        # Second click pair: right.
        assert events[3].button is MouseButton.RIGHT
        assert events[3].event_type is MouseEventType.BUTTON_DOWN
        assert events[4].event_type is MouseEventType.BUTTON_UP


class TestUpdateCamera:
    def test_stops_streams_and_persists_camera_swap(
        self,
        populated_profile_manager,
        fake_camera_controller,
        fake_inference_controller,
        camera,
    ):
        from powermouse.domain.models.camera import Camera
        import numpy as np

        new_cam = Camera(
            name="Other",
            id="1",
            fps=15.0,
            current_frame=np.zeros((4, 4, 3), dtype=np.uint8),
            frame_width=4,
            frame_height=4,
        )

        track_face.update_camera(
            camera_controller=fake_camera_controller,
            inference_controller=fake_inference_controller,
            profile_manager=populated_profile_manager,
            camera=new_cam,
        )

        assert fake_camera_controller.stop_calls == 1
        assert fake_inference_controller.stop_calls == 1
        active = populated_profile_manager.get_active_profile()
        # The persisted profile should reference the new camera identity.
        assert active.face_tracker_settings.camera.id == "1"
        assert active.face_tracker_settings.camera.name == "Other"

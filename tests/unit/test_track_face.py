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

    def test_drains_but_does_not_dispatch_gestures_when_clicking_disabled(
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
            gesture_clicking_enabled=lambda: False,
        )

        events = recording_mouse_controller.events
        assert len(events) == 1
        assert events[0].event_type is MouseEventType.MOVE
        assert inference.detect_gesture() is None


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


class TestTrackingStepRecovery:
    def test_skips_frame_when_camera_paused(
        self,
        sync_dispatch,
        fake_camera_controller,
        fake_inference_controller,
        recording_mouse_controller,
    ):
        """A paused stream (e.g. recovery panel open) must not crash the loop."""
        fake_camera_controller.fail_update = True
        translator = GestureToMouseTranslator()

        # Should not raise; the tick is silently skipped.
        track_face.tracking_step(
            camera_controller=fake_camera_controller,
            inference_controller=fake_inference_controller,
            mouse_controller=recording_mouse_controller,
            gesture_translator=translator,
            frame_processor=lambda *_: None,
        )

        # Nothing downstream of the failed read should have happened.
        assert fake_inference_controller.process_calls == []
        assert recording_mouse_controller.events == []


class TestTryStartCamera:
    def test_returns_true_on_success(
        self, fake_camera_controller, fake_inference_controller
    ):
        ok, reason = track_face.try_start_camera(
            fake_camera_controller, fake_inference_controller
        )
        assert ok is True
        assert reason is None
        assert fake_camera_controller.start_calls == 1
        assert fake_inference_controller.start_calls == 1

    def test_returns_false_with_reason_on_runtime_error(
        self, fake_camera_controller, fake_inference_controller, camera
    ):
        fake_camera_controller.fail_for_ids[camera.id] = (
            "Failed to open camera at index 1400"
        )
        ok, reason = track_face.try_start_camera(
            fake_camera_controller, fake_inference_controller
        )
        assert ok is False
        assert reason == "Failed to open camera at index 1400"
        # Inference must NOT be started when camera fails.
        assert fake_inference_controller.start_calls == 0


class TestSwapCamera:
    def _make_other(self, **overrides):
        from powermouse.domain.models.camera import Camera
        import numpy as np

        defaults = dict(
            name="Other",
            id="1",
            fps=15.0,
            current_frame=np.zeros((4, 4, 3), dtype=np.uint8),
            frame_width=4,
            frame_height=4,
        )
        defaults.update(overrides)
        return Camera(**defaults)

    def test_success_swaps_starts_and_persists(
        self,
        populated_profile_manager,
        fake_camera_controller,
        fake_inference_controller,
    ):
        new_cam = self._make_other()

        ok, reason = track_face.swap_camera(
            fake_camera_controller,
            fake_inference_controller,
            populated_profile_manager,
            new_cam,
        )

        assert (ok, reason) == (True, None)
        # Stream is stopped and restarted on the new camera.
        assert fake_camera_controller.stop_calls == 1
        assert fake_camera_controller.start_calls == 1
        assert fake_camera_controller.camera.id == new_cam.id
        # Profile was updated.
        active = populated_profile_manager.get_active_profile()
        assert active.face_tracker_settings.camera.id == new_cam.id

    def test_failure_does_not_persist(
        self,
        populated_profile_manager,
        fake_camera_controller,
        fake_inference_controller,
    ):
        broken = self._make_other(name="Broken", id="1400")
        fake_camera_controller.fail_for_ids[broken.id] = "boom"

        # Capture original camera id from the profile.
        original_id = (
            populated_profile_manager.get_active_profile()
            .face_tracker_settings.camera.id
        )

        ok, reason = track_face.swap_camera(
            fake_camera_controller,
            fake_inference_controller,
            populated_profile_manager,
            broken,
        )

        assert ok is False
        assert reason == "boom"
        # Profile must be untouched on failure.
        active = populated_profile_manager.get_active_profile()
        assert active.face_tracker_settings.camera.id == original_id

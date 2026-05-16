"""Shared pytest fixtures.

These fixtures use the real ``powermouse.adapters`` implementations where
practical so the tests exercise the same surface the application does.
"""
from __future__ import annotations

import threading
from typing import List

import numpy as np
import pytest

from powermouse.adapters.profile import SqlAlchemyProfileManager
from powermouse.domain.controllers.camera import CameraController
from powermouse.domain.controllers.devices import DeviceManager
from powermouse.domain.controllers.inference import InferenceController
from powermouse.domain.controllers.mouse import MouseController
from powermouse.domain.models.camera import Camera, FaceTrackerSettings
from powermouse.domain.models.gesture import GestureEvent
from powermouse.domain.models.mouse import ClickInterface, MouseEvent
from powermouse.domain.models.profile import Profile


# ---------------------------------------------------------------------------
# Domain-model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def blank_frame() -> np.ndarray:
    return np.zeros((48, 64, 3), dtype=np.uint8)


@pytest.fixture
def camera(blank_frame) -> Camera:
    return Camera(
        name="Test Camera",
        id="0",
        fps=30.0,
        current_frame=blank_frame,
        frame_width=blank_frame.shape[1],
        frame_height=blank_frame.shape[0],
    )


@pytest.fixture
def face_tracker_settings(camera) -> FaceTrackerSettings:
    return FaceTrackerSettings(camera=camera)


@pytest.fixture
def sample_profile(face_tracker_settings) -> Profile:
    return Profile(
        profile_id=0,
        name="Default",
        face_tracker_settings=face_tracker_settings,
        is_active=True,
        click_interfaces={ClickInterface.GESTURE: True},
    )


# ---------------------------------------------------------------------------
# Adapter fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def profile_manager() -> SqlAlchemyProfileManager:
    """SqlAlchemyProfileManager backed by an in-memory SQLite DB."""
    return SqlAlchemyProfileManager(db_url="sqlite:///:memory:")


@pytest.fixture
def populated_profile_manager(profile_manager, sample_profile) -> SqlAlchemyProfileManager:
    profile_manager.create_profile(sample_profile)
    return profile_manager


# ---------------------------------------------------------------------------
# Test doubles for controllers used by use cases / widgets.
# ---------------------------------------------------------------------------


class FakeCameraController(CameraController):
    def __init__(self, camera: Camera, frames: List[np.ndarray] | None = None):
        super().__init__(camera)
        self._frames = list(frames) if frames else [camera.current_frame]
        self._idx = 0
        self.start_calls = 0
        self.stop_calls = 0
        self.update_calls = 0

    def start_stream(self) -> None:
        self.start_calls += 1

    def stop_stream(self) -> None:
        self.stop_calls += 1

    def update_frame(self) -> None:
        self.update_calls += 1
        frame = self._frames[self._idx % len(self._frames)]
        self._idx += 1
        self.camera.update_frame(frame)


class FakeInferenceController(InferenceController):
    def __init__(
        self,
        cursor: tuple[int, int] = (10, 20),
        gestures: List[GestureEvent] | None = None,
    ):
        super().__init__()
        self._cursor = cursor
        self._gestures: List[GestureEvent] = list(gestures or [])
        self.process_calls: list[tuple[np.ndarray, int]] = []
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1

    def process_frame(self, frame_bgr, timestamp_ms: int) -> None:
        self.process_calls.append((frame_bgr, timestamp_ms))

    def get_cursor_position(self) -> tuple[int, int]:
        return self._cursor

    def detect_gesture(self):
        if not self._gestures:
            return None
        return self._gestures.pop(0)


class RecordingMouseController(MouseController):
    def __init__(self) -> None:
        self.events: list[MouseEvent] = []
        self._lock = threading.Lock()

    def handle_event(self, mouse: MouseEvent) -> None:
        with self._lock:
            self.events.append(mouse)


class FakeDeviceManager(DeviceManager):
    def __init__(self, cameras: List[Camera]):
        self._cameras = cameras

    def get_devices(self) -> List[Camera]:
        return list(self._cameras)


@pytest.fixture
def fake_camera_controller(camera) -> FakeCameraController:
    return FakeCameraController(camera)


@pytest.fixture
def fake_inference_controller() -> FakeInferenceController:
    return FakeInferenceController()


@pytest.fixture
def recording_mouse_controller() -> RecordingMouseController:
    return RecordingMouseController()


@pytest.fixture
def fake_device_manager(camera) -> FakeDeviceManager:
    return FakeDeviceManager([camera])

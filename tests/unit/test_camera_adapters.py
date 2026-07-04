from __future__ import annotations

from types import SimpleNamespace

import cv2
import pytest

from powermouse.adapters import camera as camera_adapter
from powermouse.adapters import devices as devices_adapter
from powermouse.adapters.camera import OpenCVCameraController
from powermouse.adapters.devices import SystemDeviceManager
from powermouse.domain.models.camera import Camera


class FakeCapture:
    def __init__(self, opened: bool = True):
        self._opened = opened
        self.released = False

    def isOpened(self) -> bool:
        return self._opened

    def get(self, prop: int) -> float:
        values = {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_WIDTH: 640.0,
            cv2.CAP_PROP_FRAME_HEIGHT: 480.0,
        }
        return values.get(prop, 0.0)

    def release(self) -> None:
        self.released = True


def test_open_cv_controller_normalizes_legacy_backend_offset_id(
    monkeypatch: pytest.MonkeyPatch, blank_frame
):
    calls: list[tuple[int, int]] = []

    def video_capture(index: int, backend: int):
        calls.append((index, backend))
        return FakeCapture()

    monkeypatch.setattr(camera_adapter.cv2, "VideoCapture", video_capture)

    camera = Camera(
        name="Built-in Camera",
        id=str(cv2.CAP_AVFOUNDATION),
        fps=0.0,
        current_frame=blank_frame,
        frame_width=0,
        frame_height=0,
    )
    controller = OpenCVCameraController(camera, backend=cv2.CAP_AVFOUNDATION)

    controller.start_stream()

    assert calls == [(0, cv2.CAP_AVFOUNDATION)]
    assert camera.fps == 30.0
    assert camera.frame_width == 640
    assert camera.frame_height == 480


def test_system_device_manager_enumerates_with_backend_specific_indexes(
    monkeypatch: pytest.MonkeyPatch,
):
    enumerate_calls: list[int] = []
    capture_calls: list[tuple[int, int]] = []

    def enumerate_cameras(backend: int):
        enumerate_calls.append(backend)
        return [
            SimpleNamespace(index=0, name="Built-in Camera"),
            SimpleNamespace(index=1, name="USB Camera"),
        ]

    def video_capture(index: int, backend: int):
        capture_calls.append((index, backend))
        return FakeCapture()

    monkeypatch.setattr(devices_adapter, "enumerate_cameras", enumerate_cameras)
    monkeypatch.setattr(devices_adapter.cv2, "VideoCapture", video_capture)

    manager = SystemDeviceManager(backend=cv2.CAP_AVFOUNDATION)

    cameras = manager.get_devices()

    assert enumerate_calls == [cv2.CAP_AVFOUNDATION]
    assert capture_calls == [(0, cv2.CAP_AVFOUNDATION), (1, cv2.CAP_AVFOUNDATION)]
    assert [camera.id for camera in cameras] == ["0", "1"]
    assert [camera.name for camera in cameras] == ["Built-in Camera", "USB Camera"]

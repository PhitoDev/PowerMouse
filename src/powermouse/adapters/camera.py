from __future__ import annotations

from typing import List, Optional

import cv2
import numpy as np

from powermouse.domain.controllers.camera import CameraController
from powermouse.domain.models.camera import Camera


_EMPTY_FRAME = np.zeros((0, 0, 3), dtype=np.uint8)


def _platform_backend() -> int:
    import sys
    if sys.platform.startswith("win"):
        return cv2.CAP_DSHOW
    if sys.platform == "darwin":
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_ANY


def probe_cameras(max_index: int = 10) -> List[Camera]:
    """Probe camera indices and return a list of available devices.

    OpenCV does not expose a portable enumerate API, so this opens each
    index in turn and collects the ones that succeed. Safe to call before
    any OpenCVCameraController instance exists (used by onboarding).
    """
    found: List[Camera] = []
    backend = _platform_backend()
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, backend)
        try:
            if not cap.isOpened():
                continue
            fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            found.append(
                Camera(
                    name=f"Camera {idx}",
                    id=str(idx),
                    fps=float(fps),
                    current_frame=_EMPTY_FRAME.copy(),
                    frame_width=width,
                    frame_height=height,
                )
            )
        finally:
            cap.release()
    return found


class OpenCVCameraController(CameraController):
    """OpenCV-backed CameraController using cv2.VideoCapture."""

    def __init__(self, camera: Camera, backend: Optional[int] = None):
        super().__init__(camera)
        self._backend = backend if backend is not None else _platform_backend()
        self._capture: Optional[cv2.VideoCapture] = None

    def list_cameras(self, max_index: int = 10) -> List[Camera]:  # type: ignore[override]
        """Probe camera indices and return a list of available devices."""
        return probe_cameras(max_index)

    def start_stream(self) -> None:
        if self._capture is not None and self._capture.isOpened():
            return
        try:
            index = int(self.camera.id)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Camera id must be an integer-like string, got {self.camera.id!r}"
            ) from exc
        cap = cv2.VideoCapture(index, self._backend)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"Failed to open camera at index {index}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        self.camera.fps = float(fps)
        self.camera.frame_width = width
        self.camera.frame_height = height
        self._capture = cap

    def update_frame(self) -> None:
        if self._capture is None or not self._capture.isOpened():
            raise RuntimeError("Camera stream is not started. Call start_stream() first.")
        ret, frame = self._capture.read()
        if not ret or frame is None:
            raise RuntimeError("Failed to read frame from camera")
        self.camera.update_frame(frame)

    def stop_stream(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "OpenCVCameraController":
        self.start_stream()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop_stream()

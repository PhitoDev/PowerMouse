from __future__ import annotations

import os
import queue
import threading
from typing import Dict, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np

from powermouse.domain.controllers.inference import InferenceController
from powermouse.domain.models.camera import FaceTrackerSettings
from powermouse.domain.models.gesture import GestureEvent


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# MediaPipe FaceLandmarker nose-tip index (478-point face mesh).
_NOSE_LANDMARK_INDEX = 1

# Environment variable pointing at the .task model file.
_MODEL_ENV_VAR = "POWERMOUSE_FACE_LANDMARKER_MODEL"

# Blendshape category name -> domain GestureEvent (see docs/architecture.md §4.2).
_BLENDSHAPE_TO_GESTURE: Dict[str, GestureEvent] = {
    "eyeBlinkLeft": GestureEvent.LEFT_BLINK,
    "eyeBlinkRight": GestureEvent.RIGHT_BLINK,
    "eyeSquintLeft": GestureEvent.LEFT_SQUINT,
    "eyeSquintRight": GestureEvent.RIGHT_SQUINT,
    "browInnerUp": GestureEvent.RAISED_EYEBROWS,
    "jawOpen": GestureEvent.OPEN_MOUTH,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _HysteresisGate:
    """Dual-threshold Schmitt trigger for click stability (docs §5.3)."""

    def __init__(self, high: float, low: float):
        if low > high:
            raise ValueError("low threshold must be <= high threshold")
        self._high = high
        self._low = low
        self._active = False

    def update(self, score: float) -> Optional[str]:
        if not self._active and score > self._high:
            self._active = True
            return "down"
        if self._active and score < self._low:
            self._active = False
            return "up"
        return None


class _SmoothnessEngine:
    """EMA + deadzone + non-linear acceleration (docs §5.1, §5.2)."""

    def __init__(self, settings: FaceTrackerSettings, screen_size: Tuple[int, int]):
        self._settings = settings
        self._screen_w, self._screen_h = screen_size
        # Initialize smoothed state at screen center.
        self._smoothed_x: float = self._screen_w / 2.0
        self._smoothed_y: float = self._screen_h / 2.0

    @property
    def alpha(self) -> float:
        # Higher smoothness -> more weight on history -> smaller alpha.
        # Clamp so smoothness=1 does not freeze the cursor.
        s = max(0.0, min(1.0, float(self._settings.smoothness)))
        return max(0.05, min(1.0, 1.0 - s))

    def update(self, target_x: float, target_y: float) -> Tuple[int, int]:
        cx = self._screen_w / 2.0
        cy = self._screen_h / 2.0
        dx = target_x - cx
        dy = target_y - cy
        radius = float(np.hypot(dx, dy))

        deadzone = float(self._settings.deadzone_radius_px)
        if radius <= deadzone:
            # Inside deadzone: hold last smoothed position.
            return int(round(self._smoothed_x)), int(round(self._smoothed_y))

        # Normalize direction vector.
        ux = dx / radius
        uy = dy / radius

        # Radial offset past the deadzone, normalized by half the screen diagonal.
        max_offset = float(np.hypot(cx, cy))
        offset_past_deadzone = radius - deadzone
        max_past_deadzone = max(1.0, max_offset - deadzone)
        normalized = min(1.0, offset_past_deadzone / max_past_deadzone)

        # Non-linear acceleration curve: v_out = v_in ^ n.
        exponent = max(0.1, float(self._settings.acceleration))
        accelerated = normalized ** exponent

        # Apply per-axis sensitivity and global speed gain.
        sx, sy = self._settings.sensitivity
        speed = max(0.0, float(self._settings.speed))
        gain = accelerated * speed * max_past_deadzone

        adj_x = cx + ux * gain * float(sx)
        adj_y = cy + uy * gain * float(sy)

        # Clamp to screen bounds.
        adj_x = max(0.0, min(float(self._screen_w - 1), adj_x))
        adj_y = max(0.0, min(float(self._screen_h - 1), adj_y))

        # EMA smoothing.
        a = self.alpha
        self._smoothed_x = a * adj_x + (1.0 - a) * self._smoothed_x
        self._smoothed_y = a * adj_y + (1.0 - a) * self._smoothed_y

        return int(round(self._smoothed_x)), int(round(self._smoothed_y))


def _map_nose_to_screen(
    nose_x: float,
    nose_y: float,
    screen_size: Tuple[int, int],
    active_area_x: Tuple[float, float],
    active_area_y: Tuple[float, float],
) -> Tuple[float, float]:
    """Active-area clip + normalize -> raw target pixel coordinates (docs §4.1)."""
    screen_w, screen_h = screen_size
    x_min, x_max = active_area_x
    y_min, y_max = active_area_y

    # Invert X so the cursor follows head motion like a mirror.
    raw_x = 1.0 - float(nose_x)
    raw_y = float(nose_y)

    clipped_x = min(max(raw_x, x_min), x_max)
    clipped_y = min(max(raw_y, y_min), y_max)

    span_x = max(1e-6, x_max - x_min)
    span_y = max(1e-6, y_max - y_min)
    mapped_x = (clipped_x - x_min) / span_x
    mapped_y = (clipped_y - y_min) / span_y

    return mapped_x * screen_w, mapped_y * screen_h


# ---------------------------------------------------------------------------
# Public adapter
# ---------------------------------------------------------------------------


class MediaPipeInferenceController(InferenceController):
    """MediaPipe FaceLandmarker adapter in LIVE_STREAM mode."""

    def __init__(
        self,
        settings: FaceTrackerSettings,
        screen_size: Tuple[int, int],
        model_path: Optional[str] = None,
        num_faces: int = 1,
    ):
        super().__init__()
        self._settings = settings
        self._screen_size = screen_size
        self._num_faces = num_faces

        resolved_model = model_path or os.environ.get(_MODEL_ENV_VAR)
        if not resolved_model:
            raise RuntimeError(
                f"FaceLandmarker model path not provided; pass model_path or set "
                f"{_MODEL_ENV_VAR} to the .task file location."
            )
        if not os.path.isfile(resolved_model):
            raise FileNotFoundError(f"FaceLandmarker model file not found: {resolved_model}")
        self._model_path = resolved_model

        self._smoothness = _SmoothnessEngine(settings, screen_size)
        self._gates: Dict[str, _HysteresisGate] = {
            name: _HysteresisGate(
                high=settings.click_threshold_high,
                low=settings.click_threshold_low,
            )
            for name in _BLENDSHAPE_TO_GESTURE
        }

        self._lock = threading.Lock()
        self._latest_cursor: Tuple[int, int] = (screen_size[0] // 2, screen_size[1] // 2)
        self._gesture_queue: "queue.Queue[GestureEvent]" = queue.Queue()

        self._landmarker = None  # type: ignore[assignment]

    # -- lifecycle -----------------------------------------------------

    def start(self) -> None:
        if self._landmarker is not None:
            return
        base_options = mp.tasks.BaseOptions(model_asset_path=self._model_path)
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.LIVE_STREAM,
            num_faces=self._num_faces,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=False,
            result_callback=self._on_result,
        )
        self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)

    def stop(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None

    def __enter__(self) -> "MediaPipeInferenceController":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    # -- InferenceController API ---------------------------------------

    def process_frame(self, frame_bgr: np.ndarray, timestamp_ms: int) -> None:
        if self._landmarker is None:
            raise RuntimeError("Inference is not started. Call start() first.")
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._landmarker.detect_async(mp_image, timestamp_ms)

    def get_cursor_position(self) -> Tuple[int, int]:
        with self._lock:
            return self._latest_cursor

    def detect_gesture(self) -> Optional[GestureEvent]:
        try:
            return self._gesture_queue.get_nowait()
        except queue.Empty:
            return None

    # -- MediaPipe callback (runs on MediaPipe worker thread) ----------

    def _on_result(self, result, output_image, timestamp_ms: int) -> None:
        face_landmarks_list = getattr(result, "face_landmarks", None)
        if not face_landmarks_list:
            return
        landmarks = face_landmarks_list[0]
        if len(landmarks) <= _NOSE_LANDMARK_INDEX:
            return

        nose = landmarks[_NOSE_LANDMARK_INDEX]
        target_x, target_y = _map_nose_to_screen(
            nose.x,
            nose.y,
            self._screen_size,
            self._settings.active_area_x,
            self._settings.active_area_y,
        )

        with self._lock:
            cursor = self._smoothness.update(target_x, target_y)
            self._latest_cursor = cursor

        blendshapes_list = getattr(result, "face_blendshapes", None)
        if not blendshapes_list:
            return
        for category in blendshapes_list[0]:
            gesture = _BLENDSHAPE_TO_GESTURE.get(category.category_name)
            if gesture is None:
                continue
            edge = self._gates[category.category_name].update(float(category.score))
            if edge == "down":
                self._gesture_queue.put(gesture)

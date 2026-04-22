from __future__ import annotations

from typing import Optional

import numpy as np

from powermouse.domain.models.gesture import GestureEvent


class InferenceController:
    def __init__(
        self,
    ):
        pass

    def process_frame(self, frame_bgr: np.ndarray, timestamp_ms: int) -> None:
        raise NotImplementedError

    def get_cursor_position(self) -> tuple[int, int]:
        raise NotImplementedError

    def detect_gesture(self) -> Optional[GestureEvent]:
        raise NotImplementedError

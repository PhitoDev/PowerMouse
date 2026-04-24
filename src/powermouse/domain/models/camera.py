from dataclasses import dataclass

import numpy as np


@dataclass
class Camera:
    name: str
    id: str
    fps: float
    current_frame: np.ndarray
    frame_width: int
    frame_height: int

    def update_frame(self, frame: np.ndarray):
        self.current_frame = frame
        self.frame_width = frame.shape[1]
        self.frame_height = frame.shape[0]


@dataclass
class FaceTrackerSettings:
    camera: Camera
    speed: float = 1.0
    acceleration: float = 1.5
    sensitivity: tuple[float, float] = (1.0, 1.0)
    smoothness: float = 0.5
    # Signal-processing thresholds (see docs/architecture.md §5).
    deadzone_radius_px: int = 5
    active_area_x: tuple[float, float] = (0.4, 0.6)
    active_area_y: tuple[float, float] = (0.4, 0.6)
    click_threshold_high: float = 0.6
    click_threshold_low: float = 0.4

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

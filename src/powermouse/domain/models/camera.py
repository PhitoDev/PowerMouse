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
    speed: float
    acceleration: float
    sensitivity: float
    smoothness: float

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

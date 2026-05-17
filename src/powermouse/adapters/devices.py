import platform

import cv2
import numpy as np
from cv2_enumerate_cameras import enumerate_cameras

from powermouse.domain.controllers.devices import DeviceManager
from powermouse.domain.models.camera import Camera

_EMPTY_FRAME = np.zeros((0, 0, 3), dtype=np.uint8)


class SystemDeviceManager(DeviceManager):
    def __init__(self):
        self.os = platform.system()

    def get_devices(self) -> list[Camera]:
        devices = self._enumerate_devices()
        cameras = []

        for i, name in devices.items():
            cap = cv2.VideoCapture(i)
            fps = cap.get(cv2.CAP_PROP_FPS)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            cap.release()
            frame = _EMPTY_FRAME
            cameras.append(
                Camera(
                    name=name,
                    id=str(i),
                    fps=fps,
                    frame_height=int(height),
                    frame_width=int(width),
                    current_frame=frame,
                )
            )
        return cameras

    def _enumerate_devices(self) -> dict[int, str]:
        camera_dict = {}

        for info in enumerate_cameras():
            if info.name not in camera_dict.values():
                camera_dict[info.index] = info.name

        return camera_dict

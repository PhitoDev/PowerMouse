import glob
import os
import platform

import cv2
import numpy as np
from pygrabber.dshow_graph import FilterGraph

from powermouse.domain.controllers.devices import DeviceManager
from powermouse.domain.models.camera import Camera

_EMPTY_FRAME = np.zeros((0, 0, 3), dtype=np.uint8)


class SystemDeviceManager(DeviceManager):
    def __init__(self):
        self.os = platform.system()

    def get_devices(self) -> list[Camera]:
        devices = {}
        cameras = []
        match self.os:
            case "Linux":
                devices = self._get_devices_linux()
            case "Windows":
                devices = self._get_devices_windows()
            case _:
                raise NotImplementedError(f"Unsupported OS: {self.os}")

        for i, name in devices.items():
            cap = cv2.VideoCapture(i)
            fps = cap.get(cv2.CAP_PROP_FPS)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
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

    def _get_devices_linux(self) -> dict[int, str]:
        cameras = {}
        # Find all video devices
        device_paths = glob.glob("/sys/class/video4linux/video*")

        for path in device_paths:
            # The index is the number at the end of 'video0', 'video1', etc.
            index = int(os.path.basename(path).replace("video", ""))

            # Read the human-readable name from the 'name' file
            with open(os.path.join(path, "name"), "r") as f:
                name = f.read().strip()

            cameras[index] = name
            print(f"OpenCV Index {index}: {name}")

        return cameras

    def _get_devices_windows(self) -> dict[int, str]:
        graph = FilterGraph()
        devices = graph.get_input_devices()
        return {i: device for i, device in enumerate(devices)}

# pyright: reportGeneralTypeIssues=false, reportArgumentType=false
from __future__ import annotations

import cv2
import dearpygui.dearpygui as dpg
import numpy as np


class CameraWidget:
    """Live camera preview panel. Owns a raw texture updated from the tracking loop."""

    TAG = "camera_panel"
    TEXTURE_TAG = "camera_texture"

    def __init__(self, panel_width: int = 640, image_width: int = 624, image_height: int = 352):
        self._panel_w = panel_width
        self._img_w = image_width
        self._img_h = image_height
        self._blank = np.zeros(self._img_w * self._img_h * 4, dtype=np.float32)

    def build(self, parent: str) -> None:
        with dpg.texture_registry(show=False):
            dpg.add_raw_texture(
                width=self._img_w,
                height=self._img_h,
                default_value=self._blank,
                tag=self.TEXTURE_TAG,
                format=dpg.mvFormat_Float_rgba,
            )
        with dpg.child_window(tag=self.TAG, parent=parent, width=self._panel_w, border=True):
            dpg.add_text("Camera Preview")
            dpg.add_separator()
            dpg.add_image(self.TEXTURE_TAG)

    def update_frame(self, frame_bgr: np.ndarray, timestamp_ms: int) -> None:  # noqa: ARG002
        if frame_bgr is None or frame_bgr.size == 0:
            return
        resized = cv2.resize(frame_bgr, (self._img_w, self._img_h), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        rgba = np.empty((self._img_h, self._img_w, 4), dtype=np.float32)
        rgba[..., 0:3] = rgb
        rgba[..., 3] = 1.0
        dpg.set_value(self.TEXTURE_TAG, rgba.ravel())

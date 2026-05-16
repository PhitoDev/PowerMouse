"""Integration tests for :class:`powermouse.widgets.camera.CameraWidget`."""
from __future__ import annotations

import dearpygui.dearpygui as dpg
import numpy as np

from powermouse.widgets.camera import CameraWidget


def _build_widget(camera, controllers, manager) -> CameraWidget:
    return CameraWidget(
        camera_controller=controllers["camera"],
        inference_controller=controllers["inference"],
        profile_manager=manager,
        current_camera=camera,
        cameras=[camera],
        panel_width=320,
        image_width=64,
        image_height=48,
    )


class TestCameraWidget:
    def test_build_creates_texture_and_combo(
        self,
        dpg_root,
        camera,
        fake_camera_controller,
        fake_inference_controller,
        populated_profile_manager,
    ):
        widget = _build_widget(
            camera,
            {"camera": fake_camera_controller, "inference": fake_inference_controller},
            populated_profile_manager,
        )
        widget.build(dpg_root)
        assert dpg.does_item_exist(widget.TAG)
        assert dpg.does_item_exist(widget.TEXTURE_TAG)
        assert dpg.does_item_exist(widget.CAMERA_TAG)

    def test_update_frame_does_not_error_on_valid_frame(
        self,
        dpg_root,
        camera,
        fake_camera_controller,
        fake_inference_controller,
        populated_profile_manager,
    ):
        widget = _build_widget(
            camera,
            {"camera": fake_camera_controller, "inference": fake_inference_controller},
            populated_profile_manager,
        )
        widget.build(dpg_root)
        frame = np.full((48, 64, 3), 200, dtype=np.uint8)
        # update_frame writes into the raw texture; success = no exception.
        widget.update_frame(frame, 0)
        assert dpg.does_item_exist(widget.TEXTURE_TAG)

    def test_update_frame_ignores_empty_input(
        self,
        dpg_root,
        camera,
        fake_camera_controller,
        fake_inference_controller,
        populated_profile_manager,
    ):
        widget = _build_widget(
            camera,
            {"camera": fake_camera_controller, "inference": fake_inference_controller},
            populated_profile_manager,
        )
        widget.build(dpg_root)
        # Must not raise on empty arrays.
        widget.update_frame(np.zeros((0, 0, 3), dtype=np.uint8), 0)
        widget.update_frame(None, 0)  # type: ignore[arg-type]

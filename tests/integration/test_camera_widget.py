"""Integration tests for :class:`powermouse.widgets.camera.CameraWidget`."""
from __future__ import annotations

import dearpygui.dearpygui as dpg
import numpy as np

from powermouse.domain.models.camera import Camera
from powermouse.widgets.camera import CameraWidget


def _build_widget(
    camera, controllers, manager, cameras=None, device_manager=None
) -> CameraWidget:
    return CameraWidget(
        camera_controller=controllers["camera"],
        inference_controller=controllers["inference"],
        profile_manager=manager,
        device_manager=device_manager,
        current_camera=camera,
        cameras=cameras if cameras is not None else [camera],
        panel_width=320,
        image_width=64,
        image_height=48,
    )


def _make_camera(name="Other", id="1") -> Camera:
    return Camera(
        name=name,
        id=id,
        fps=15.0,
        current_frame=np.zeros((4, 4, 3), dtype=np.uint8),
        frame_width=4,
        frame_height=4,
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

    def test_combo_change_persists_camera_and_notifies_listener(
        self,
        dpg_root,
        camera,
        fake_camera_controller,
        fake_inference_controller,
        populated_profile_manager,
    ):
        other = _make_camera(name="Other", id="1")
        changed: list[Camera] = []
        widget = CameraWidget(
            camera_controller=fake_camera_controller,
            inference_controller=fake_inference_controller,
            profile_manager=populated_profile_manager,
            current_camera=camera,
            cameras=[camera, other],
            panel_width=320,
            image_width=64,
            image_height=48,
            on_camera_changed=changed.append,
        )
        widget.build(dpg_root)

        dpg.set_value(widget.CAMERA_TAG, other.name)
        widget._on_combo_change()

        reloaded = populated_profile_manager.get_active_profile()
        assert reloaded.face_tracker_settings.camera.id == other.id
        assert reloaded.face_tracker_settings.camera.name == other.name
        assert changed == [other]


class TestCameraWidgetRecovery:
    """Recovery panel that's shown when the camera can't be opened."""

    def test_start_success_keeps_preview_visible(
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
        # Camera will start successfully.
        fake_camera_controller.stop_stream()  # ensure we test start path

        assert widget.start() is True
        assert widget.in_recovery is False
        assert dpg.is_item_shown(widget.PREVIEW_GROUP_TAG)
        assert not dpg.is_item_shown(widget.RECOVERY_GROUP_TAG)

    def test_start_failure_shows_recovery_panel(
        self,
        dpg_root,
        camera,
        fake_camera_controller,
        fake_inference_controller,
        populated_profile_manager,
    ):
        # Make the saved camera fail to open (the bug from the log file).
        fake_camera_controller.fail_for_ids[camera.id] = (
            "Failed to open camera at index 1400"
        )
        widget = _build_widget(
            camera,
            {"camera": fake_camera_controller, "inference": fake_inference_controller},
            populated_profile_manager,
        )
        widget.build(dpg_root)

        ok = widget.start()

        assert ok is False
        assert widget.in_recovery is True
        # Recovery panel visible, preview hidden.
        assert dpg.is_item_shown(widget.RECOVERY_GROUP_TAG)
        assert not dpg.is_item_shown(widget.PREVIEW_GROUP_TAG)
        # Body message identifies the missing camera.
        body = dpg.get_value(widget.RECOVERY_BODY_TAG)
        assert camera.name in body
        # Technical-details line carries the raw reason.
        assert "Failed to open camera at index 1400" in dpg.get_value(
            widget.RECOVERY_DETAILS_TAG
        )
        # The primary action is disabled until a camera is picked.
        assert (
            dpg.get_item_configuration(widget.RECOVERY_USE_TAG)["enabled"] is False
        )

    def test_recovery_lists_detected_cameras_and_marks_saved_missing(
        self,
        dpg_root,
        camera,
        fake_camera_controller,
        fake_inference_controller,
        populated_profile_manager,
    ):
        working = _make_camera(name="Integrated Webcam", id="0")
        # Saved camera (`camera`, id="0"... wait fixture uses id "0").
        # Use a saved camera that is NOT in the detected list to assert "missing".
        saved = _make_camera(name="HD Pro Webcam", id="1400")
        fake_camera_controller.camera = saved
        fake_camera_controller.fail_for_ids[saved.id] = "missing"

        widget = _build_widget(
            saved,
            {"camera": fake_camera_controller, "inference": fake_inference_controller},
            populated_profile_manager,
            cameras=[working],
        )
        widget.build(dpg_root)
        widget.start()

        # Selectables exist for each detected camera.
        children = dpg.get_item_children(widget.RECOVERY_LIST_TAG, slot=1) or []
        labels = [dpg.get_item_label(c) for c in children]
        assert any("Integrated Webcam" in (l or "") for l in labels)
        # And a "Missing: ..." marker for the saved camera.
        assert any("Missing" in (l or "") and "HD Pro Webcam" in (l or "") for l in labels) \
            or any(
                "Missing" in (dpg.get_value(c) or "")
                and "HD Pro Webcam" in (dpg.get_value(c) or "")
                for c in children
            )

    def test_use_this_camera_recovers_and_persists(
        self,
        dpg_root,
        camera,
        fake_camera_controller,
        fake_inference_controller,
        populated_profile_manager,
    ):
        fake_camera_controller.fail_for_ids[camera.id] = "boom"
        working = _make_camera(name="Integrated Webcam", id="0_alt")

        widget = _build_widget(
            camera,
            {"camera": fake_camera_controller, "inference": fake_inference_controller},
            populated_profile_manager,
            cameras=[working],
        )
        widget.build(dpg_root)
        widget.start()
        assert widget.in_recovery is True

        # User picks the working camera and clicks "Use this camera".
        widget._on_select_recovery(working)
        assert (
            dpg.get_item_configuration(widget.RECOVERY_USE_TAG)["enabled"] is True
        )
        widget._on_use_selected()

        # Recovery dismissed.
        assert widget.in_recovery is False
        assert dpg.is_item_shown(widget.PREVIEW_GROUP_TAG)
        assert not dpg.is_item_shown(widget.RECOVERY_GROUP_TAG)
        # Active profile now references the recovered camera.
        active = populated_profile_manager.get_active_profile()
        assert active.face_tracker_settings.camera.id == working.id

    def test_use_this_camera_keeps_recovery_open_on_failure(
        self,
        dpg_root,
        camera,
        fake_camera_controller,
        fake_inference_controller,
        populated_profile_manager,
    ):
        fake_camera_controller.fail_for_ids[camera.id] = "boom"
        also_broken = _make_camera(name="Also broken", id="9999")
        fake_camera_controller.fail_for_ids[also_broken.id] = "still broken"

        widget = _build_widget(
            camera,
            {"camera": fake_camera_controller, "inference": fake_inference_controller},
            populated_profile_manager,
            cameras=[also_broken],
        )
        widget.build(dpg_root)
        widget.start()

        widget._on_select_recovery(also_broken)
        widget._on_use_selected()

        # Still in recovery; profile NOT updated.
        assert widget.in_recovery is True
        active = populated_profile_manager.get_active_profile()
        assert active.face_tracker_settings.camera.id == camera.id
        assert "still broken" in dpg.get_value(widget.RECOVERY_DETAILS_TAG)

    def test_refresh_devices_rescans_via_device_manager(
        self,
        dpg_root,
        camera,
        fake_camera_controller,
        fake_inference_controller,
        populated_profile_manager,
    ):
        from tests.conftest import FakeDeviceManager

        fake_camera_controller.fail_for_ids[camera.id] = "boom"
        # Device manager starts empty, then gains a camera.
        dm = FakeDeviceManager([])
        widget = _build_widget(
            camera,
            {"camera": fake_camera_controller, "inference": fake_inference_controller},
            populated_profile_manager,
            cameras=[],
            device_manager=dm,
        )
        widget.build(dpg_root)
        widget.start()

        # Initially no cameras detected.
        children = dpg.get_item_children(widget.RECOVERY_LIST_TAG, slot=1) or []
        assert all(
            "No cameras detected" in (dpg.get_value(c) or "")
            or "Missing" in (dpg.get_value(c) or "")
            for c in children
        )

        # User plugs in a camera; FakeDeviceManager now reports it.
        plugged = _make_camera(name="Plugged-in cam", id="2")
        dm._cameras = [plugged]
        widget._on_refresh_devices()

        children = dpg.get_item_children(widget.RECOVERY_LIST_TAG, slot=1) or []
        labels = [dpg.get_item_label(c) for c in children]
        assert any("Plugged-in cam" in (l or "") for l in labels)
        # Internal cache is updated.
        assert any(c.id == plugged.id for c in widget._cameras)

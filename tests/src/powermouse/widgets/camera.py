# pyright: reportGeneralTypeIssues=false, reportArgumentType=false
from __future__ import annotations

from typing import Callable, Optional

import cv2
import dearpygui.dearpygui as dpg
import numpy as np

from powermouse.domain.controllers.camera import CameraController
from powermouse.domain.controllers.devices import DeviceManager
from powermouse.domain.controllers.inference import InferenceController
from powermouse.domain.controllers.profile import ProfileManager
from powermouse.domain.models.camera import Camera
from powermouse.domain.usecases.track_face import swap_camera, try_start_camera
from powermouse.widgets.style import (
    add_alert_heading,
    add_body_text,
    add_field_label,
    add_panel_heading,
    add_section_heading,
)


class CameraWidget:
    """Live camera preview panel.

    Owns a raw texture updated from the tracking loop. When the active
    camera can't be opened (e.g. the saved camera index is no longer
    present), the preview is replaced by an inline *recovery panel* that
    lists detected cameras, lets the user pick a working one, and updates
    the active profile accordingly.
    """

    TAG = "camera_panel"
    TEXTURE_TAG = "camera_texture"
    CAMERA_TAG = "camera_combo"
    PREVIEW_GROUP_TAG = "camera_preview_group"
    RECOVERY_GROUP_TAG = "camera_recovery_group"
    RECOVERY_TITLE_TAG = "camera_recovery_title"
    RECOVERY_BODY_TAG = "camera_recovery_body"
    RECOVERY_LIST_TAG = "camera_recovery_list"
    RECOVERY_DETAILS_TAG = "camera_recovery_details"
    RECOVERY_USE_TAG = "camera_recovery_use"
    RECOVERY_REFRESH_TAG = "camera_recovery_refresh"
    PANEL_INNER_PADDING_PX = 32

    def __init__(
        self,
        camera_controller: CameraController,
        inference_controller: InferenceController,
        profile_manager: ProfileManager,
        current_camera: Camera,
        cameras: list[Camera],
        device_manager: DeviceManager | None = None,
        panel_width: int = 640,
        image_width: int = 624,
        image_height: int = 352,
        on_camera_changed: Callable[[Camera], None] = lambda _camera: None,
    ):
        self._panel_w = panel_width
        content_w = max(1, panel_width - self.PANEL_INNER_PADDING_PX)
        if image_width > content_w:
            image_height = max(1, int(image_height * (content_w / image_width)))
            image_width = content_w
        self._content_w = content_w
        self._img_w = image_width
        self._img_h = image_height
        self._blank = np.zeros(self._img_w * self._img_h * 4, dtype=np.float32)
        self._camera_controller = camera_controller
        self._inference_controller = inference_controller
        self._profile_manager = profile_manager
        self._device_manager = device_manager
        self._cameras = cameras
        self._current_camera = current_camera
        self._on_camera_changed = on_camera_changed
        self._selected_recovery: Optional[Camera] = None
        self._last_failure: Optional[str] = None
        self.in_recovery = False

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, parent: str) -> None:

        with dpg.texture_registry(show=False):
            dpg.add_raw_texture(
                width=self._img_w,
                height=self._img_h,
                default_value=self._blank,
                tag=self.TEXTURE_TAG,
                format=dpg.mvFormat_Float_rgba,
            )
        with dpg.child_window(
            tag=self.TAG, parent=parent, width=self._panel_w, border=True
        ):
            # Normal preview group
            with dpg.group(tag=self.PREVIEW_GROUP_TAG):
                add_panel_heading(self.PREVIEW_GROUP_TAG, "Camera")
                add_field_label(self.PREVIEW_GROUP_TAG, "Current Camera")
                dpg.add_combo(
                    label="",
                    items=[cam.name for cam in self._cameras],
                    tag=self.CAMERA_TAG,
                    default_value=self._current_camera.name,
                    width=-1,
                    callback=self._on_combo_change,
                )
                dpg.add_separator()
                add_section_heading(self.PREVIEW_GROUP_TAG, "Camera Preview")
                dpg.add_image(self.TEXTURE_TAG)
                dpg.add_separator()
                add_body_text(self.PREVIEW_GROUP_TAG, f"FPS: {self._current_camera.fps}")

            # Recovery panel (hidden until needed)
            with dpg.group(tag=self.RECOVERY_GROUP_TAG, show=False):
                add_alert_heading(
                    self.RECOVERY_GROUP_TAG,
                    "We couldn't reach your camera",
                    tag=self.RECOVERY_TITLE_TAG,
                )
                add_body_text(
                    self.RECOVERY_GROUP_TAG,
                    "PowerMouse is paused until a working camera is selected.",
                    tag=self.RECOVERY_BODY_TAG,
                    wrap=self._content_w,
                )
                dpg.add_separator()
                add_section_heading(self.RECOVERY_GROUP_TAG, "Available cameras")
                with dpg.group(tag=self.RECOVERY_LIST_TAG):
                    pass  # populated dynamically
                dpg.add_separator()
                dpg.add_button(
                    label="Refresh devices",
                    tag=self.RECOVERY_REFRESH_TAG,
                    width=-1,
                    callback=self._on_refresh_devices,
                )
                dpg.add_button(
                    label="Use this camera",
                    tag=self.RECOVERY_USE_TAG,
                    width=-1,
                    callback=self._on_use_selected,
                    enabled=False,
                )
                dpg.add_separator()
                dpg.add_text(
                    "",
                    tag=self.RECOVERY_DETAILS_TAG,
                    color=(139, 148, 158),
                    wrap=self._content_w,
                )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Start the camera + inference pipeline.

        If the camera can't be opened, switches into the recovery state
        instead of raising. Returns ``True`` when streaming, ``False`` when
        the recovery panel is shown.
        """
        ok, reason = try_start_camera(
            self._camera_controller, self._inference_controller
        )
        if ok:
            self._hide_recovery()
            return True
        self._show_recovery(reason)
        return False

    def refresh_devices(self) -> None:
        """Rescan cameras and refresh camera-selection controls."""
        self._on_refresh_devices()

    # ------------------------------------------------------------------
    # Frame updates
    # ------------------------------------------------------------------

    def update_frame(self, frame_bgr: np.ndarray, timestamp_ms: int) -> None:  # noqa: ARG002
        if frame_bgr is None or frame_bgr.size == 0:
            return
        if self.in_recovery:
            return
        resized = cv2.resize(
            frame_bgr, (self._img_w, self._img_h), interpolation=cv2.INTER_AREA
        )
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        rgba = np.empty((self._img_h, self._img_w, 4), dtype=np.float32)
        rgba[..., 0:3] = rgb
        rgba[..., 3] = 1.0
        dpg.set_value(self.TEXTURE_TAG, rgba.ravel())

    # ------------------------------------------------------------------
    # Combo callback (happy-path camera switching)
    # ------------------------------------------------------------------

    def _on_combo_change(self) -> None:
        name = dpg.get_value(self.CAMERA_TAG)
        cam = next((c for c in self._cameras if c.name == name), None)
        if cam is None:
            return
        ok, reason = swap_camera(
            self._camera_controller,
            self._inference_controller,
            self._profile_manager,
            cam,
        )
        if ok:
            self._current_camera = cam
            self._on_camera_changed(cam)
            self._hide_recovery()
        else:
            self._show_recovery(reason)

    # ------------------------------------------------------------------
    # Recovery panel
    # ------------------------------------------------------------------

    def _show_recovery(self, reason: Optional[str]) -> None:
        self.in_recovery = True
        self._last_failure = reason
        if dpg.does_item_exist(self.RECOVERY_GROUP_TAG):
            dpg.show_item(self.RECOVERY_GROUP_TAG)
        if dpg.does_item_exist(self.PREVIEW_GROUP_TAG):
            dpg.hide_item(self.PREVIEW_GROUP_TAG)
        if dpg.does_item_exist(self.RECOVERY_BODY_TAG):
            dpg.set_value(
                self.RECOVERY_BODY_TAG,
                (
                    f"Your saved camera '{self._current_camera.name}' "
                    f"(id={self._current_camera.id}) isn't available right now. "
                    "Pick another camera to keep going — your profile will remember it."
                ),
            )
        if dpg.does_item_exist(self.RECOVERY_DETAILS_TAG):
            dpg.set_value(
                self.RECOVERY_DETAILS_TAG,
                f"Technical details: {reason}" if reason else "",
            )
        self._refresh_recovery_list()

    def _hide_recovery(self) -> None:
        self.in_recovery = False
        self._last_failure = None
        self._selected_recovery = None
        if dpg.does_item_exist(self.RECOVERY_GROUP_TAG):
            dpg.hide_item(self.RECOVERY_GROUP_TAG)
        if dpg.does_item_exist(self.PREVIEW_GROUP_TAG):
            dpg.show_item(self.PREVIEW_GROUP_TAG)
        # Keep the combo in sync with the active camera.
        if dpg.does_item_exist(self.CAMERA_TAG):
            dpg.configure_item(
                self.CAMERA_TAG, items=[cam.name for cam in self._cameras]
            )
            dpg.set_value(self.CAMERA_TAG, self._current_camera.name)

    def _refresh_recovery_list(self) -> None:
        if not dpg.does_item_exist(self.RECOVERY_LIST_TAG):
            return
        # Clear and rebuild the list of detected cameras.
        for child in dpg.get_item_children(self.RECOVERY_LIST_TAG, slot=1) or []:
            dpg.delete_item(child)

        detected_ids = {c.id for c in self._cameras}
        saved_present = self._current_camera.id in detected_ids

        if not self._cameras:
            dpg.add_text(
                "No cameras detected. Plug one in and click Refresh devices.",
                parent=self.RECOVERY_LIST_TAG,
                color=(139, 148, 158),
            )
        else:
            for cam in self._cameras:
                label = f"{cam.name}  (id={cam.id})"
                dpg.add_selectable(
                    label=label,
                    parent=self.RECOVERY_LIST_TAG,
                    callback=lambda s, a, u: self._on_select_recovery(u),
                    user_data=cam,
                    default_value=(
                        self._selected_recovery is not None
                        and self._selected_recovery.id == cam.id
                    ),
                )

        if not saved_present:
            dpg.add_text(
                f"Missing: {self._current_camera.name} (id={self._current_camera.id})",
                parent=self.RECOVERY_LIST_TAG,
                color=(248, 81, 73),
            )

        if dpg.does_item_exist(self.RECOVERY_USE_TAG):
            dpg.configure_item(
                self.RECOVERY_USE_TAG, enabled=self._selected_recovery is not None
            )

    def _on_select_recovery(self, cam: Camera) -> None:
        self._selected_recovery = cam
        self._refresh_recovery_list()

    def _on_use_selected(self) -> None:
        if self._selected_recovery is None:
            return
        cam = self._selected_recovery
        ok, reason = swap_camera(
            self._camera_controller,
            self._inference_controller,
            self._profile_manager,
            cam,
        )
        if ok:
            self._current_camera = cam
            self._on_camera_changed(cam)
            if cam not in self._cameras:
                self._cameras.append(cam)
            self._hide_recovery()
        else:
            self._show_recovery(reason)

    def _on_refresh_devices(self) -> None:
        if self._device_manager is None:
            self._refresh_recovery_list()
            return
        try:
            self._cameras = self._device_manager.get_devices()
        except Exception as exc:  # pragma: no cover - device-enum failure path
            self._last_failure = str(exc)
        self._selected_recovery = None
        if dpg.does_item_exist(self.CAMERA_TAG):
            dpg.configure_item(
                self.CAMERA_TAG,
                items=[cam.name for cam in self._cameras],
            )
            if any(cam.id == self._current_camera.id for cam in self._cameras):
                dpg.set_value(self.CAMERA_TAG, self._current_camera.name)
        self._refresh_recovery_list()

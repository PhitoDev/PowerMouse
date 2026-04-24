# pyright: reportGeneralTypeIssues=false, reportArgumentType=false
"""First-run onboarding flow.

Per requirements §2 Onboarding: prompts the user to create a profile with a
name + camera selection, then persists it via the profile manager. Runs in its
own DPG context so the main app can start fresh once a profile exists.
"""
from __future__ import annotations

from typing import List, Optional

import dearpygui.dearpygui as dpg

from powermouse.adapters.camera import OpenCVCameraController
from powermouse.adapters.profile import SqlAlchemyProfileManager
from powermouse.domain.models.camera import Camera, FaceTrackerSettings
from powermouse.domain.models.mouse import ClickInterface
from powermouse.domain.models.profile import Profile


_GESTURE_CHEAT_SHEET = [
    ("Wink left eye", "Left click"),
    ("Wink right eye", "Right click"),
    ("Squint left eye", "Double click"),
    ("Squint right eye", "Toggle hold right click (drag)"),
    ("Raise eyebrows", "Middle click"),
    ("Open jaw", "Toggle hold left click (drag)"),
]


class OnboardingDialog:
    """Self-contained first-run dialog. Owns its DPG context lifecycle."""

    WINDOW_TAG = "onboarding_window"
    NAME_TAG = "onboarding_name"
    CAMERA_TAG = "onboarding_camera"
    STATUS_TAG = "onboarding_status"
    CREATE_TAG = "onboarding_create"
    RETRY_TAG = "onboarding_retry"

    def __init__(self, profile_manager: SqlAlchemyProfileManager):
        self._manager = profile_manager
        self._cameras: List[Camera] = []
        self._created: Optional[Profile] = None

    # -- entry point ---------------------------------------------------

    def run(self) -> Profile:
        """Display the dialog and return the created profile. Raises SystemExit if the
        user closes the viewport without completing."""
        dpg.create_context()
        try:
            dpg.create_viewport(title="PowerMouse Setup", width=560, height=620)
            dpg.setup_dearpygui()
            self._build()
            dpg.set_primary_window(self.WINDOW_TAG, True)
            dpg.show_viewport()
            # Probe cameras on the first frame so the UI is visible immediately.
            self._refresh_cameras()
            while dpg.is_dearpygui_running():
                dpg.render_dearpygui_frame()
                if self._created is not None:
                    break
        finally:
            dpg.destroy_context()

        if self._created is None:
            raise SystemExit("Onboarding cancelled; no profile was created.")
        return self._created

    # -- DPG tree ------------------------------------------------------

    def _build(self) -> None:
        with dpg.window(tag=self.WINDOW_TAG, no_scrollbar=False, no_title_bar=True):
            dpg.add_text("Welcome to PowerMouse", color=(200, 220, 255))
            dpg.add_text(
                "Let's set up your first profile. You can create more later from the main window.",
                wrap=520,
            )
            dpg.add_separator()

            dpg.add_text("Profile Name")
            dpg.add_input_text(tag=self.NAME_TAG, hint="e.g. Default", width=-1)

            dpg.add_spacer(height=6)
            dpg.add_text("Camera")
            dpg.add_combo(
                tag=self.CAMERA_TAG,
                items=[],
                width=-1,
                default_value="Detecting cameras...",
            )
            dpg.add_button(label="Retry camera detection", tag=self.RETRY_TAG,
                           callback=self._refresh_cameras)

            dpg.add_spacer(height=10)
            dpg.add_separator()
            dpg.add_text("Gesture Clicking (always on for now)", color=(200, 220, 255))
            dpg.add_text("These facial gestures trigger clicks once tracking starts:", wrap=520)
            with dpg.table(header_row=True, policy=dpg.mvTable_SizingStretchProp):
                dpg.add_table_column(label="Gesture")
                dpg.add_table_column(label="Action")
                for gesture, action in _GESTURE_CHEAT_SHEET:
                    with dpg.table_row():
                        dpg.add_text(gesture)
                        dpg.add_text(action)

            dpg.add_spacer(height=10)
            dpg.add_separator()
            dpg.add_text("", tag=self.STATUS_TAG, color=(255, 160, 160))
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Create Profile",
                    tag=self.CREATE_TAG,
                    callback=self._on_create,
                    enabled=False,
                )
                dpg.add_button(label="Cancel", callback=lambda: dpg.stop_dearpygui())

    # -- camera probing ------------------------------------------------

    def _refresh_cameras(self, *_):
        self._set_status("Detecting cameras...")
        dpg.configure_item(self.CREATE_TAG, enabled=False)
        # Synchronous probe. list_cameras() opens each index briefly; a few
        # seconds tops. Doing it inline keeps the implementation simple; the
        # user sees the status text until it returns.
        try:
            cameras = OpenCVCameraController.list_cameras()
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Camera detection failed: {exc}")
            return

        self._cameras = cameras
        if not cameras:
            dpg.configure_item(
                self.CAMERA_TAG,
                items=[],
                default_value="No cameras detected",
            )
            self._set_status(
                "No cameras detected. Please connect a webcam and click Retry."
            )
            dpg.configure_item(self.CREATE_TAG, enabled=False)
            return

        labels = [f"{cam.name} (id={cam.id})" for cam in cameras]
        dpg.configure_item(self.CAMERA_TAG, items=labels, default_value=labels[0])
        self._set_status("")
        dpg.configure_item(self.CREATE_TAG, enabled=True)

    # -- create handler ------------------------------------------------

    def _on_create(self, *_):
        name = (dpg.get_value(self.NAME_TAG) or "").strip()
        if not name:
            self._set_status("Profile name is required.")
            return
        if len(name) > 64:
            self._set_status("Profile name must be 64 characters or fewer.")
            return
        if not self._cameras:
            self._set_status("A camera must be selected.")
            return

        selection_label = dpg.get_value(self.CAMERA_TAG)
        labels = [f"{cam.name} (id={cam.id})" for cam in self._cameras]
        try:
            idx = labels.index(selection_label)
        except ValueError:
            self._set_status("Please pick a camera from the list.")
            return
        camera = self._cameras[idx]

        settings = FaceTrackerSettings(camera=camera)
        profile = Profile(
            profile_id=0,
            name=name,
            face_tracker_settings=settings,
            is_active=True,
            click_interfaces={ClickInterface.GESTURE: True},
        )
        try:
            created = self._manager.create_profile(profile)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Failed to save profile: {exc}")
            return

        self._created = created
        dpg.stop_dearpygui()

    # -- helpers -------------------------------------------------------

    def _set_status(self, message: str) -> None:
        if dpg.does_item_exist(self.STATUS_TAG):
            dpg.set_value(self.STATUS_TAG, message)


def run_onboarding(profile_manager: SqlAlchemyProfileManager) -> Profile:
    """Convenience helper: run the dialog once and return the created profile."""
    return OnboardingDialog(profile_manager).run()

# pyright: reportGeneralTypeIssues=false, reportArgumentType=false
from __future__ import annotations

import os

import dearpygui.dearpygui as dpg
from screeninfo import get_monitors

from powermouse.adapters.camera import OpenCVCameraController
from powermouse.adapters.devices import SystemDeviceManager
from powermouse.adapters.inference import MediaPipeInferenceController
from powermouse.adapters.mouse import SystemMouseController
from powermouse.adapters.profile import SqlAlchemyProfileManager
from powermouse.widgets.camera import CameraWidget
from powermouse.widgets.onboarding import run_onboarding
from powermouse.widgets.profiles import ProfilesWidget
from powermouse.widgets.settings import (
    ClickingSettingsWidget,
    SettingsWidget,
    TrackingSettingsWidget,
)

from .domain.usecases.gesture_mapping import GestureToMouseTranslator
from .domain.usecases.track_face import tracking_step

FONT_PATH = os.path.join(
    os.path.dirname(__file__), "resources/JetBrainsMonoNLNerdFontMono-Bold.ttf"
)
assert os.path.exists(FONT_PATH), f"Font file not found: {FONT_PATH}"


def main() -> None:
    monitor = get_monitors()[0]
    profile_manager = SqlAlchemyProfileManager()
    device_manager = SystemDeviceManager()

    # First-run onboarding when no profiles exist.
    if not profile_manager.list_profiles():
        run_onboarding(profile_manager, device_manager)

    try:
        active_profile = profile_manager.get_active_profile()
    except LookupError:
        # Profiles exist but none is active; pick the first one and activate it.
        profiles = profile_manager.list_profiles()
        if not profiles:
            raise SystemExit("No profiles available after onboarding; exiting.")
        first = profiles[0]
        first.is_active = True
        active_profile = profile_manager.update_profile(first.profile_id, first)

    camera_controller = OpenCVCameraController(
        camera=active_profile.face_tracker_settings.camera,
    )
    inference_controller = MediaPipeInferenceController(
        settings=active_profile.face_tracker_settings,
        screen_size=(monitor.width, monitor.height),
    )
    mouse_controller = SystemMouseController()
    gesture_translator = GestureToMouseTranslator()

    camera_controller.start_stream()
    inference_controller.start()

    # Widgets ----------------------------------------------------------
    camera_widget = CameraWidget(
        camera_controller=camera_controller,
        inference_controller=inference_controller,
        profile_manager=profile_manager,
        cameras=device_manager.get_devices(),
        current_camera=active_profile.face_tracker_settings.camera,
        panel_width=640,
        image_width=624,
        image_height=352,
    )
    tracking_widget = TrackingSettingsWidget()
    clicking_widget = ClickingSettingsWidget()
    settings_widget = SettingsWidget(
        profile_manager=profile_manager,
        tracking=tracking_widget,
        clicking=clicking_widget,
    )
    profiles_widget = ProfilesWidget(
        profile_manager=profile_manager,
        on_selection_changed=settings_widget.bind,
    )

    # DPG setup --------------------------------------------------------
    dpg.create_context()

    with dpg.font_registry():
        default_font = dpg.add_font(FONT_PATH, 20)

    dpg.bind_font(default_font)

    with dpg.window(tag="root", no_scrollbar=True) as root:
        with dpg.group(horizontal=True):
            profiles_widget.build(parent=root)
            camera_widget.build(parent=root)
            settings_widget.build(parent=root)

    # dpg.show_font_manager()
    dpg.set_primary_window("root", True)

    # Initial selection triggers settings.bind(), which populates the tabs.
    profiles_widget.select_initial()

    dpg.create_viewport(title="PowerMouse", width=1280, height=720)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    try:
        while dpg.is_dearpygui_running():
            tracking_step(
                frame_processor=camera_widget.update_frame,
                mouse_controller=mouse_controller,
                inference_controller=inference_controller,
                camera_controller=camera_controller,
                gesture_translator=gesture_translator,
            )
            dpg.render_dearpygui_frame()
    finally:
        inference_controller.stop()
        camera_controller.stop_stream()
        dpg.destroy_context()


if __name__ == "__main__":
    main()

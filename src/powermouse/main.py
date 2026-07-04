# pyright: reportGeneralTypeIssues=false, reportArgumentType=false
from __future__ import annotations

import sys
import threading
import time

import dearpygui.dearpygui as dpg
from screeninfo import get_monitors

from powermouse.adapters.camera import OpenCVCameraController
from powermouse.adapters.devices import SystemDeviceManager
from powermouse.adapters.inference import MediaPipeInferenceController
from powermouse.adapters.mouse import SystemMouseController
from powermouse.adapters.profile import SqlAlchemyProfileManager
from powermouse.theme import setup_theme
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


DEFAULT_VIEWPORT_SIZE = (1280, 720)
SCREEN_MARGIN_PX = 80
PROFILES_PANEL_WIDTH = 240
MIN_SETTINGS_PANEL_WIDTH = 280
MIN_CAMERA_PANEL_WIDTH = 240
LAYOUT_MARGIN_PX = 48
CAMERA_PANEL_PADDING_PX = 16
CAMERA_PREVIEW_ASPECT_RATIO = 16 / 9
CAMERA_VERTICAL_CHROME_PX = 220
SHORTCUT_HANDLER_TAG = "global_shortcut_handlers"


def _shortcut_modifier_down() -> bool:
    """Return true when Command on macOS, or Control elsewhere, is held."""
    return any(
        dpg.is_key_down(key)
        for key in (
            dpg.mvKey_LWin,
            dpg.mvKey_RWin,
            dpg.mvKey_LControl,
            dpg.mvKey_RControl,
        )
    )


def _shift_down() -> bool:
    return dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)


def _run_shortcut(callback, *, shift_required: bool = False) -> None:
    if not _shortcut_modifier_down():
        return
    if shift_required and not _shift_down():
        return
    if not shift_required and _shift_down():
        return
    callback()


def _register_keyboard_shortcuts(
    profiles_widget: ProfilesWidget,
    camera_widget: CameraWidget,
    settings_widget: SettingsWidget,
) -> None:
    """Install global shortcuts used by Apple Voice Control custom commands."""
    with dpg.handler_registry(tag=SHORTCUT_HANDLER_TAG):
        dpg.add_key_press_handler(
            key=dpg.mvKey_N,
            callback=lambda *_: _run_shortcut(profiles_widget.new_profile),
        )
        dpg.add_key_press_handler(
            key=dpg.mvKey_S,
            callback=lambda *_: _run_shortcut(settings_widget.save),
        )
        dpg.add_key_press_handler(
            key=dpg.mvKey_R,
            callback=lambda *_: _run_shortcut(settings_widget.revert),
        )
        dpg.add_key_press_handler(
            key=dpg.mvKey_R,
            callback=lambda *_: _run_shortcut(
                camera_widget.refresh_devices,
                shift_required=True,
            ),
        )
        dpg.add_key_press_handler(
            key=dpg.mvKey_Return,
            callback=lambda *_: _run_shortcut(profiles_widget.set_active_selected),
        )
        dpg.add_key_press_handler(
            key=dpg.mvKey_Delete,
            callback=lambda *_: _run_shortcut(profiles_widget.delete_selected),
        )
        dpg.add_key_press_handler(
            key=dpg.mvKey_1,
            callback=lambda *_: _run_shortcut(settings_widget.select_tracking_tab),
        )
        dpg.add_key_press_handler(
            key=dpg.mvKey_2,
            callback=lambda *_: _run_shortcut(settings_widget.select_clicking_tab),
        )


def _viewport_size(monitor) -> tuple[int, int]:
    """Return a main viewport size that stays inside the active display."""
    max_width = max(1, monitor.width - SCREEN_MARGIN_PX)
    max_height = max(1, monitor.height - SCREEN_MARGIN_PX)
    return (
        min(DEFAULT_VIEWPORT_SIZE[0], max_width),
        min(DEFAULT_VIEWPORT_SIZE[1], max_height),
    )


def _camera_layout(viewport_width: int, viewport_height: int) -> tuple[int, int, int]:
    """Scale the camera panel so the three-column UI fits in the viewport."""
    max_panel_width = max(
        MIN_CAMERA_PANEL_WIDTH,
        viewport_width
        - PROFILES_PANEL_WIDTH
        - MIN_SETTINGS_PANEL_WIDTH
        - LAYOUT_MARGIN_PX,
    )
    panel_width = min(640, max_panel_width)

    max_image_width = max(1, panel_width - CAMERA_PANEL_PADDING_PX)
    max_image_height = max(1, viewport_height - CAMERA_VERTICAL_CHROME_PX)
    image_width = min(
        624,
        max_image_width,
        int(max_image_height * CAMERA_PREVIEW_ASPECT_RATIO),
    )
    image_height = max(1, int(image_width / CAMERA_PREVIEW_ASPECT_RATIO))
    panel_width = max(MIN_CAMERA_PANEL_WIDTH, image_width + CAMERA_PANEL_PADDING_PX)

    return panel_width, image_width, image_height


def main() -> None:
    monitor = get_monitors()[0]
    viewport_width, viewport_height = _viewport_size(monitor)
    camera_panel_width, camera_image_width, camera_image_height = _camera_layout(
        viewport_width,
        viewport_height,
    )
    # Testing mode: start every app run with a clean profile database.
    profile_manager = SqlAlchemyProfileManager(reset_db=True)
    device_manager = SystemDeviceManager()

    # First-run onboarding when no profiles exist.
    if not profile_manager.list_profiles():
        created = run_onboarding(profile_manager, device_manager)
        if created is None:
            # User cancelled / closed the onboarding window. Exit cleanly with
            # status 0 and no stderr output -- on Briefcase Windows MSI builds
            # the stub treats stderr writes during shutdown as a crash.
            sys.exit(0)

    try:
        active_profile = profile_manager.get_active_profile()
    except LookupError:
        # Profiles exist but none is active; pick the first one and activate it.
        profiles = profile_manager.list_profiles()
        if not profiles:
            sys.exit(0)
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

    # Widgets ----------------------------------------------------------
    camera_widget = CameraWidget(
        camera_controller=camera_controller,
        inference_controller=inference_controller,
        profile_manager=profile_manager,
        device_manager=device_manager,
        cameras=device_manager.get_devices(),
        current_camera=active_profile.face_tracker_settings.camera,
        panel_width=camera_panel_width,
        image_width=camera_image_width,
        image_height=camera_image_height,
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
    setup_theme()

    with dpg.window(tag="root", no_scrollbar=True):
        with dpg.group(horizontal=True) as main_row:
            profiles_widget.build(parent=main_row)
            camera_widget.build(parent=main_row)
            settings_widget.build(parent=main_row)
    _register_keyboard_shortcuts(profiles_widget, camera_widget, settings_widget)

    # dpg.show_font_manager()
    dpg.set_primary_window("root", True)

    # Initial selection triggers settings.bind(), which populates the tabs.
    profiles_widget.select_initial()

    # Start the camera + inference pipeline. If the saved camera can't be
    # opened (e.g. was unplugged), the widget switches into a recovery
    # state instead of crashing the app.
    camera_widget.start()

    dpg.create_viewport(
        title="PowerMouse",
        width=viewport_width,
        height=viewport_height,
    )
    dpg.setup_dearpygui()
    dpg.show_viewport()

    # Create a background thread for tracking
    def background_tracking_loop():
        while dpg.is_dearpygui_running():
            tracking_step(
                frame_processor=camera_widget.update_frame,
                mouse_controller=mouse_controller,
                inference_controller=inference_controller,
                camera_controller=camera_controller,
                gesture_translator=gesture_translator,
            )

            time.sleep(0.005)

    tracking_thread = threading.Thread(target=background_tracking_loop, daemon=True)
    tracking_thread.start()

    try:
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
    finally:
        inference_controller.stop()
        camera_controller.stop_stream()
        dpg.destroy_context()


if __name__ == "__main__":
    main()

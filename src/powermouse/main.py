# pyright: reportGeneralTypeIssues=false, reportArgumentType=false
from __future__ import annotations

import queue
import sys
import threading
import time

import dearpygui.dearpygui as dpg
from screeninfo import get_monitors

from powermouse.adapters.camera import OpenCVCameraController
from powermouse.adapters.devices import SystemDeviceManager
from powermouse.adapters.dwell_palette import SubprocessDwellPalette
from powermouse.adapters.inference import MediaPipeInferenceController
from powermouse.adapters.mouse import SystemMouseController
from powermouse.adapters.profile import SqlAlchemyProfileManager
from powermouse.adapters.voice import (
    RecognitionWorker,
    SoundDeviceMicrophoneCapture,
    SoundDeviceMicrophoneManager,
    VoskSpeechRecognizer,
)
from powermouse.domain.models.mouse import ClickInterface
from powermouse.domain.models.microphone import Microphone
from powermouse.theme import setup_theme
from powermouse.widgets.camera import CameraWidget
from powermouse.widgets.onboarding import run_onboarding
from powermouse.widgets.profiles import ProfilesWidget
from powermouse.widgets.settings import (
    ClickingSettingsWidget,
    SettingsWidget,
    TrackingSettingsWidget,
)

from .domain.usecases.dwell_clicking import DwellClicker, dwell_clicking_step
from .domain.usecases.gesture_mapping import GestureToMouseTranslator
from .domain.usecases.mouse_actions import MouseActionCoordinator
from .domain.usecases.track_face import tracking_step
from .domain.usecases.voice_clicking import VoiceToMouseTranslator, voice_clicking_step


DEFAULT_VIEWPORT_SIZE = (1280, 720)
SCREEN_MARGIN_PX = 80
PROFILES_PANEL_WIDTH = 240
MIN_SETTINGS_PANEL_WIDTH = 280
MIN_CAMERA_PANEL_WIDTH = 240
LAYOUT_MARGIN_PX = 48
CAMERA_PANEL_PADDING_PX = 32
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
    profile_manager = SqlAlchemyProfileManager(reset_db=False)
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
    action_coordinator = MouseActionCoordinator()
    gesture_translator = GestureToMouseTranslator(action_coordinator)
    voice_translator = VoiceToMouseTranslator(action_coordinator)
    dwell_palette = SubprocessDwellPalette()
    dwell_clicker = DwellClicker(
        settings=active_profile.dwell_settings,
        palette=dwell_palette,
        coordinator=action_coordinator,
    )
    microphone_manager = SoundDeviceMicrophoneManager()
    microphone_capture = SoundDeviceMicrophoneCapture()
    speech_recognizer = VoskSpeechRecognizer()
    recognition_worker = RecognitionWorker(microphone_capture, speech_recognizer)
    voice_lock = threading.Lock()
    voice_release_requests: queue.SimpleQueue[threading.Event | None] = (
        queue.SimpleQueue()
    )
    shutting_down = False
    runtime_voice_enabled = False
    runtime_dwell_enabled = False
    running_profile_id: int | None = None
    running_microphone: Microphone | None = None

    def request_voice_hold_release(acknowledged: threading.Event | None = None):
        voice_release_requests.put(acknowledged)

    def apply_voice_profile(profile):
        nonlocal runtime_voice_enabled
        nonlocal running_profile_id
        nonlocal running_microphone

        with voice_lock:
            if shutting_down:
                return False

            # Editing an inactive profile never changes the live runtime.
            if profile is not None and not profile.is_active:
                clicking_widget.set_status(
                    "inactive profile — applies when activated"
                )
                return True

            previous_enabled = runtime_voice_enabled
            previous_profile_id = running_profile_id
            previous_microphone = running_microphone

            voice_requested = bool(
                profile
                and profile.is_click_interface_enabled(ClickInterface.VOICE)
            )
            microphone = None
            discovery_error = None
            if voice_requested:
                try:
                    microphone = (
                        microphone_manager.resolve_microphone(profile.microphone)
                        if profile.microphone is not None
                        else microphone_manager.get_default_microphone()
                    )
                except Exception as exc:
                    discovery_error = exc
                    if (
                        previous_enabled
                        and previous_profile_id == profile.profile_id
                    ):
                        clicking_widget.set_status(
                            f"microphone discovery failed; still listening: {exc}"
                        )
                        return False

            if (
                voice_requested
                and microphone is not None
                and previous_enabled
                and previous_profile_id == profile.profile_id
                and previous_microphone == microphone
            ):
                clicking_widget.set_status("listening")
                return True

            runtime_voice_enabled = False
            recognition_worker.stop()
            request_voice_hold_release()
            running_profile_id = None
            running_microphone = None

            if not voice_requested:
                clicking_widget.set_status("off")
                return True

            if discovery_error is not None:
                clicking_widget.set_status(
                    f"microphone discovery failed: {discovery_error}"
                )
                return False

            if microphone is None:
                clicking_widget.set_status("unavailable")
                return False

            clicking_widget.set_status("loading")
            try:
                microphone_capture.start(microphone)
                recognition_worker.start()
            except Exception as exc:
                recognition_worker.stop()
                # A failed edit of the currently active profile should not
                # destroy its previously working voice stream.
                if (
                    previous_enabled
                    and previous_profile_id == profile.profile_id
                    and previous_microphone is not None
                ):
                    try:
                        microphone_capture.start(previous_microphone)
                        recognition_worker.start()
                    except Exception:
                        recognition_worker.stop()
                    else:
                        runtime_voice_enabled = True
                        running_profile_id = previous_profile_id
                        running_microphone = previous_microphone
                        clicking_widget.set_status(
                            f"switch failed; listening on {previous_microphone.name}"
                        )
                        return False

                clicking_widget.set_status(f"permission/open failure: {exc}")
                return False

            runtime_voice_enabled = True
            running_profile_id = profile.profile_id
            running_microphone = microphone
            clicking_widget.set_status("listening")
            return True

    def apply_dwell_profile(profile):
        """Sync the dwell runtime (clicker + palette) with the active profile.

        Called on active-profile changes and whenever dwell settings are
        edited. Editing an inactive profile never changes the live runtime.
        """
        nonlocal runtime_dwell_enabled
        if shutting_down or profile is None or not profile.is_active:
            return
        enabled = profile.is_click_interface_enabled(ClickInterface.DWELL)
        dwell_clicker.settings = profile.dwell_settings
        if enabled:
            dwell_palette.apply_settings(profile.dwell_settings)
            dwell_palette.show()
        else:
            dwell_palette.hide()
        # The dispatch worker releases dwell-owned holds when it observes the
        # disabled flag (see dwell_step below).
        runtime_dwell_enabled = enabled

    # Widgets ----------------------------------------------------------
    tracking_widget = TrackingSettingsWidget()
    clicking_widget = ClickingSettingsWidget(
        microphone_manager, apply_voice_profile, apply_dwell_profile
    )
    settings_widget = SettingsWidget(
        profile_manager=profile_manager,
        tracking=tracking_widget,
        clicking=clicking_widget,
    )
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
        on_camera_changed=settings_widget.update_active_profile_camera,
    )

    def apply_active_profile(profile):
        settings_widget.set_active_profile(profile)
        apply_dwell_profile(profile)
        return apply_voice_profile(profile)

    profiles_widget = ProfilesWidget(
        profile_manager=profile_manager,
        on_selection_changed=settings_widget.bind,
        on_active_changed=apply_active_profile,
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
    apply_voice_profile(active_profile)
    apply_dwell_profile(active_profile)

    dpg.create_viewport(
        title="PowerMouse",
        width=viewport_width,
        height=viewport_height,
    )
    dpg.setup_dearpygui()
    dpg.show_viewport()

    preview_frames: queue.Queue[tuple[object, int]] = queue.Queue(maxsize=1)

    def queue_preview_frame(frame, timestamp):
        try:
            preview_frames.put_nowait((frame, timestamp))
        except queue.Full:
            # Rendering only needs the newest frame that fits without blocking
            # the mouse-control worker.
            try:
                preview_frames.get_nowait()
            except queue.Empty:
                pass
            try:
                preview_frames.put_nowait((frame, timestamp))
            except queue.Full:
                pass

    def current_cursor() -> tuple[int, int]:
        """Cursor position for click dispatch: always the real OS cursor.

        While face tracking is on, ``tracking_step`` has already moved the OS
        cursor to the inferred position, so this stays correct in both modes
        and keeps clicking working when the camera is unavailable."""
        return mouse_controller.get_position()

    def drain_voice_releases(cursor):
        while True:
            try:
                acknowledged = voice_release_requests.get_nowait()
            except queue.Empty:
                return
            try:
                for event in voice_translator.reset_holds(cursor):
                    mouse_controller.handle_event(event)
            finally:
                if acknowledged is not None:
                    acknowledged.set()

    # Runs on the dispatch worker once per loop iteration, independent of the
    # camera pipeline, so dwell clicking keeps working when face tracking is
    # off or the camera is unavailable.
    dwell_was_active = False

    def dwell_step(cursor: tuple[int, int], timestamp: int) -> None:
        nonlocal dwell_was_active
        dwell_was_active = dwell_clicking_step(
            dwell_clicker,
            mouse_controller,
            cursor,
            timestamp,
            runtime_dwell_enabled,
            dwell_was_active,
        )

    # Camera, gesture, voice, and dwell mouse events share one dispatch worker.
    def background_tracking_loop():
        while not stop_event.is_set():
            cursor = current_cursor()
            drain_voice_releases(cursor)
            voice_clicking_step(
                speech_recognizer,
                voice_translator,
                mouse_controller,
                cursor,
                runtime_voice_enabled,
            )

            try:
                tracking_step(
                    frame_processor=queue_preview_frame,
                    mouse_controller=mouse_controller,
                    inference_controller=inference_controller,
                    camera_controller=camera_controller,
                    gesture_translator=gesture_translator,
                    tracking_enabled=settings_widget.is_tracking_enabled,
                    gesture_clicking_enabled=settings_widget.is_gesture_clicking_enabled,
                )
            except RuntimeError:
                # Voice and dwell remain available while the camera/inference
                # pipeline is temporarily unavailable.
                pass

            # Dwell runs after tracking so it sees the freshest cursor, and
            # outside tracking_step so a camera failure never stalls it.
            dwell_step(current_cursor(), int(time.time() * 1000))

            time.sleep(0.005)

    def stop_voice_after_worker_error(failure: tuple[int, str]) -> None:
        nonlocal runtime_voice_enabled
        nonlocal running_profile_id
        nonlocal running_microphone
        generation, error = failure
        with voice_lock:
            if shutting_down or generation != recognition_worker.generation:
                return
            recognition_worker.stop()
            runtime_voice_enabled = False
            running_profile_id = None
            running_microphone = None
            request_voice_hold_release()
        clicking_widget.set_status(f"recognition stopped: {error}")

    def render_latest_preview() -> None:
        latest = None
        while True:
            try:
                latest = preview_frames.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            camera_widget.update_frame(*latest)

    stop_event = threading.Event()
    tracking_thread = threading.Thread(
        target=background_tracking_loop,
        name="mouse-dispatch",
        daemon=False,
    )
    tracking_thread.start()

    try:
        while dpg.is_dearpygui_running():
            error = recognition_worker.detect_error()
            if error is not None:
                stop_voice_after_worker_error(error)
            render_latest_preview()
            dpg.render_dearpygui_frame()
    finally:
        with voice_lock:
            shutting_down = True
            recognition_worker.stop()
            runtime_voice_enabled = False
        release_acknowledged = threading.Event()
        request_voice_hold_release(release_acknowledged)
        release_acknowledged.wait(timeout=1)
        stop_event.set()
        tracking_thread.join()

        # The dispatch worker normally performs the voice release above. This
        # final idempotent cleanup also releases gesture-owned buttons and is
        # safe because the worker has already stopped.
        cursor = current_cursor()
        for translator in (voice_translator, gesture_translator):
            for event in translator.reset_holds(cursor):
                mouse_controller.handle_event(event)
        # Release any dwell-owned drag before tearing down the palette
        # subprocess so the user is never left with a stuck button.
        for event in dwell_clicker.reset_holds(cursor):
            mouse_controller.handle_event(event)
        dwell_palette.stop()
        inference_controller.stop()
        camera_controller.stop_stream()
        dpg.destroy_context()


if __name__ == "__main__":
    main()

import time
from typing import Callable

from powermouse.domain.controllers import camera, inference, mouse, profile
from powermouse.domain.models.mouse import MouseButton, MouseEvent, MouseEventType
from powermouse.domain.usecases.gesture_mapping import GestureToMouseTranslator


def _dispatch(mouse_controller: mouse.MouseController, event: MouseEvent) -> None:
    mouse_controller.handle_event(event)


def tracking_step(
    camera_controller: camera.CameraController,
    inference_controller: inference.InferenceController,
    mouse_controller: mouse.MouseController,
    gesture_translator: GestureToMouseTranslator,
    frame_processor,
    gesture_clicking_enabled: Callable[[], bool] = lambda: True,
):
    try:
        camera_controller.update_frame()
    except RuntimeError:
        # Camera stream is paused (e.g. recovery panel is open). Skip this
        # tick instead of crashing the tracking thread.
        return
    frame = camera_controller.camera.current_frame
    timestamp = int(time.time() * 1000)
    inference_controller.process_frame(frame, timestamp)

    # Move the cursor every frame.
    cursor = inference_controller.get_cursor_position()
    _dispatch(
        mouse_controller,
        MouseEvent(
            button=MouseButton.LEFT,
            x=cursor[0],
            y=cursor[1],
            event_type=MouseEventType.MOVE,
        ),
    )

    # Drain any queued gestures and dispatch their mouse events when gesture
    # clicking is enabled. Gestures are still drained while disabled so old
    # queued clicks do not fire later when the user re-enables the interface.
    while True:
        gesture = inference_controller.detect_gesture()
        if gesture is None:
            break
        if not gesture_clicking_enabled():
            continue
        for event in gesture_translator.translate(gesture, cursor):
            _dispatch(mouse_controller, event)

    frame_processor(frame, timestamp)


def update_camera(
    camera_controller: camera.CameraController,
    inference_controller: inference.InferenceController,
    profile_manager: profile.ProfileManager,
    camera: camera.Camera,
):
    camera_controller.stop_stream()
    inference_controller.stop()
    profile = profile_manager.get_active_profile()
    profile.face_tracker_settings.camera = camera
    profile_manager.update_profile(
        profile_id=profile.profile_id,
        profile=profile,
    )


def try_start_camera(
    camera_controller: camera.CameraController,
    inference_controller: inference.InferenceController,
) -> tuple[bool, str | None]:
    """Attempt to (re)start the camera + inference pipeline.

    Returns ``(True, None)`` on success or ``(False, message)`` if the camera
    couldn't be opened. Never raises for the expected device-unavailable
    cases (``RuntimeError`` / ``ValueError``) so callers can render a
    recovery UI instead of crashing.
    """
    try:
        camera_controller.start_stream()
    except (RuntimeError, ValueError) as exc:
        return False, str(exc)
    try:
        inference_controller.start()
    except Exception as exc:  # pragma: no cover - inference failure path
        camera_controller.stop_stream()
        return False, str(exc)
    return True, None


def swap_camera(
    camera_controller: camera.CameraController,
    inference_controller: inference.InferenceController,
    profile_manager: profile.ProfileManager,
    new_camera: camera.Camera,
) -> tuple[bool, str | None]:
    """Switch the active camera and restart the pipeline.

    Stops the current stream + inference, mutates the controller's camera,
    starts the new stream, and only persists the change to the active
    profile when the new camera actually opens. On failure, the profile is
    left untouched so the user can pick a different camera.
    """
    camera_controller.stop_stream()
    inference_controller.stop()
    camera_controller.camera = new_camera
    ok, reason = try_start_camera(camera_controller, inference_controller)
    if not ok:
        return False, reason
    active = profile_manager.get_active_profile()
    active.face_tracker_settings.camera = new_camera
    profile_manager.update_profile(profile_id=active.profile_id, profile=active)
    return True, None

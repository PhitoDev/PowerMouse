import threading
import time

from powermouse.domain.controllers import camera, inference, mouse, profile
from powermouse.domain.usecases.gesture_mapping import GestureToMouseTranslator
from powermouse.domain.models.mouse import MouseButton, MouseEvent, MouseEventType


def _dispatch(mouse_controller: mouse.MouseController, event: MouseEvent) -> None:
    threading.Thread(target=mouse_controller.handle_event, args=(event,)).start()


def tracking_step(
    camera_controller: camera.CameraController,
    inference_controller: inference.InferenceController,
    mouse_controller: mouse.MouseController,
    gesture_translator: GestureToMouseTranslator,
    frame_processor,
):
    camera_controller.update_frame()
    frame = camera_controller.camera.current_frame
    timestamp = int(time.time() * 1000)
    inference_controller.process_frame(frame, timestamp)

    # Move the cursor every frame.
    cursor = inference_controller.get_cursor_position()
    _dispatch(
        mouse_controller,
        MouseEvent(button=MouseButton.LEFT, x=cursor[0], y=cursor[1], event_type=MouseEventType.MOVE),
    )

    # Drain any queued gestures and dispatch their mouse events.
    while True:
        gesture = inference_controller.detect_gesture()
        if gesture is None:
            break
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

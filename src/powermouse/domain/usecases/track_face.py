import threading
import time

from powermouse.domain.controllers import camera, inference, mouse


def tracking_step(
    camera_controller: camera.CameraController,
    inference_controller: inference.InferenceController,
    mouse_controller: mouse.MouseController,
    frame_processor,
):
    camera_controller.update_frame()
    frame = camera_controller.camera.current_frame
    timestamp = int(time.time() * 1000)
    inference_controller.process_frame(frame, timestamp)
    gesture = inference_controller.detect_gesture()
    if gesture is not None:
        threading.Thread(
            target=mouse_controller.handle_event,
            args=(gesture,),
        ).start()
    frame_processor(frame, timestamp)

from powermouse.domain.models.camera import Camera


class CameraController:
    def __init__(self, camera: Camera):
        self.camera = camera

    def list_cameras(self) -> list[Camera]:
        raise NotImplementedError

    def update_frame(self):
        raise NotImplementedError

    def start_stream(self):
        raise NotImplementedError

    def stop_stream(self):
        raise NotImplementedError

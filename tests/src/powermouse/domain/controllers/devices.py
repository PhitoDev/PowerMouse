from powermouse.domain.models.camera import Camera


class DeviceManager:
    def _get_devices_linux(self) -> dict[int, str]:
        raise NotImplementedError

    def _get_devices_windows(self) -> dict[int, str]:
        raise NotImplementedError

    def get_devices(self) -> list[Camera]:
        raise NotImplementedError

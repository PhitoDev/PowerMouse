from dataclasses import dataclass, field

from .camera import FaceTrackerSettings
from .mouse import ClickInterface


@dataclass
class Profile:
    profile_id: int
    name: str
    face_tracker_settings: FaceTrackerSettings
    is_active: bool = field(default=False)
    click_interfaces: dict[ClickInterface, bool] = field(default_factory=dict)

    def set_active(self, active: bool):
        self.is_active = active

    def toggle_click_interface(self, interface: ClickInterface, enabled: bool):
        self.click_interfaces[interface] = enabled

    def is_click_interface_enabled(self, interface: ClickInterface) -> bool:
        return self.click_interfaces.get(interface, False)

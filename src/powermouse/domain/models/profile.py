from dataclasses import dataclass, field

from powermouse.domain.entities.mouse import ClickInterface

from .camera import FaceTrackerSettings


@dataclass
class Profile:
    name: str
    face_tracker_settings: FaceTrackerSettings
    click_interfaces: dict[ClickInterface, bool] = field(default_factory=dict)

    def toggle_click_interface(self, interface: ClickInterface, enabled: bool):
        self.click_interfaces[interface] = enabled

    def is_click_interface_enabled(self, interface: ClickInterface) -> bool:
        return self.click_interfaces.get(interface, False)

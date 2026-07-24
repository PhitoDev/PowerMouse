from dataclasses import dataclass, field

from .camera import FaceTrackerSettings
from .dwell import DwellSettings
from .microphone import Microphone
from .mouse import ClickInterface


@dataclass
class Profile:
    profile_id: int
    name: str
    face_tracker_settings: FaceTrackerSettings
    is_active: bool = field(default=False)
    #: Face-driven cursor movement. Off lets the user pair PowerMouse's
    #: clicking interfaces with any other pointing method.
    tracking_enabled: bool = field(default=True)
    click_interfaces: dict[ClickInterface, bool] = field(default_factory=dict)
    microphone: Microphone | None = None
    dwell_settings: DwellSettings = field(default_factory=DwellSettings)

    def set_active(self, active: bool):
        self.is_active = active

    def toggle_click_interface(self, interface: ClickInterface, enabled: bool):
        self.click_interfaces[interface] = enabled

    def is_click_interface_enabled(self, interface: ClickInterface) -> bool:
        return self.click_interfaces.get(interface, False)

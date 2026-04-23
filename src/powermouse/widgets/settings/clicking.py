from __future__ import annotations

from typing import Dict, Optional

import dearpygui.dearpygui as dpg

from powermouse.domain.models.mouse import ClickInterface
from powermouse.domain.models.profile import Profile


class ClickingSettingsWidget:
    """Clicking-configuration controls bound to a Profile (live mutation)."""

    HIGH_TAG = "clicking_threshold_high"
    LOW_TAG = "clicking_threshold_low"

    def __init__(self):
        self._profile: Optional[Profile] = None
        self._checkbox_tags: Dict[ClickInterface, str] = {
            ci: f"clicking_interface_{ci.value}" for ci in ClickInterface
        }

    def build(self, parent: str) -> None:
        dpg.add_text("Click Interfaces", parent=parent)
        for ci, tag in self._checkbox_tags.items():
            dpg.add_checkbox(
                label=ci.value.title(),
                tag=tag,
                parent=parent,
                callback=self._make_on_toggle(ci),
            )
        dpg.add_separator(parent=parent)
        dpg.add_text("Gesture Click Thresholds", parent=parent)
        dpg.add_slider_float(
            label="High", tag=self.HIGH_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.6,
            callback=self._on_high,
        )
        dpg.add_slider_float(
            label="Low", tag=self.LOW_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.4,
            callback=self._on_low,
        )

    def bind(self, profile: Profile) -> None:
        self._profile = profile
        for ci, tag in self._checkbox_tags.items():
            dpg.set_value(tag, profile.is_click_interface_enabled(ci))
        dpg.set_value(self.HIGH_TAG, profile.face_tracker_settings.click_threshold_high)
        dpg.set_value(self.LOW_TAG, profile.face_tracker_settings.click_threshold_low)

    # -- callbacks -----------------------------------------------------

    def _make_on_toggle(self, ci: ClickInterface):
        def cb(sender, app_data, user_data):  # noqa: ARG001
            if self._profile is not None:
                self._profile.toggle_click_interface(ci, bool(app_data))
        return cb

    def _on_high(self, sender, app_data, user_data):  # noqa: ARG002
        if self._profile is not None:
            self._profile.face_tracker_settings.click_threshold_high = float(app_data)

    def _on_low(self, sender, app_data, user_data):  # noqa: ARG002
        if self._profile is not None:
            self._profile.face_tracker_settings.click_threshold_low = float(app_data)

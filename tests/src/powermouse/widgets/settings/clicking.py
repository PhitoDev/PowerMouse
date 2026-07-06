from __future__ import annotations

from typing import Dict, Optional

import dearpygui.dearpygui as dpg

from powermouse.domain.models.mouse import ClickInterface
from powermouse.domain.models.profile import Profile
from powermouse.widgets.style import (
    add_body_text,
    add_field_label,
    add_gesture_cheat_sheet,
    add_section_heading,
)


class ClickingSettingsWidget:
    """Clicking-configuration controls bound to a Profile (live mutation)."""

    HIGH_TAG = "clicking_threshold_high"
    LOW_TAG = "clicking_threshold_low"
    CHEAT_SHEET_GROUP_TAG = "clicking_gesture_cheat_sheet"
    CONTROL_WIDTH = -1
    ENABLED_INTERFACES = {ClickInterface.GESTURE}

    def __init__(self):
        self._profile: Optional[Profile] = None
        self._checkbox_tags: Dict[ClickInterface, str] = {
            ci: f"clicking_interface_{ci.value}" for ci in ClickInterface
        }

    def build(self, parent: str) -> None:
        add_section_heading(parent, "Click Interfaces")
        for ci, tag in self._checkbox_tags.items():
            dpg.add_checkbox(
                label=ci.value.title(),
                tag=tag,
                parent=parent,
                enabled=ci in self.ENABLED_INTERFACES,
                callback=self._make_on_toggle(ci),
            )
        dpg.add_separator(parent=parent)
        add_section_heading(parent, "Gesture Click Thresholds")
        add_field_label(parent, "High")
        dpg.add_slider_float(
            label="", tag=self.HIGH_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.6,
            width=self.CONTROL_WIDTH,
            callback=self._on_high,
        )
        add_field_label(parent, "Low")
        dpg.add_slider_float(
            label="", tag=self.LOW_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.4,
            width=self.CONTROL_WIDTH,
            callback=self._on_low,
        )
        dpg.add_separator(parent=parent)
        add_section_heading(parent, "Gesture Clicking Cheat Sheet")
        add_body_text(
            parent,
            "These facial gestures trigger clicks once tracking starts:",
            wrap=0,
        )
        dpg.add_spacer(parent=parent, height=4)
        add_gesture_cheat_sheet(parent, tag=self.CHEAT_SHEET_GROUP_TAG)

    def bind(self, profile: Profile) -> None:
        self._profile = profile
        for ci, tag in self._checkbox_tags.items():
            dpg.set_value(tag, profile.is_click_interface_enabled(ci))
        dpg.set_value(self.HIGH_TAG, profile.face_tracker_settings.click_threshold_high)
        dpg.set_value(self.LOW_TAG, profile.face_tracker_settings.click_threshold_low)

    # -- callbacks -----------------------------------------------------

    def _make_on_toggle(self, ci: ClickInterface):
        def cb(sender, app_data, user_data):  # noqa: ARG001
            if ci not in self.ENABLED_INTERFACES:
                return
            if self._profile is not None:
                self._profile.toggle_click_interface(ci, bool(app_data))
        return cb

    def _on_high(self, sender, app_data, user_data):  # noqa: ARG002
        if self._profile is not None:
            self._profile.face_tracker_settings.click_threshold_high = float(app_data)

    def _on_low(self, sender, app_data, user_data):  # noqa: ARG002
        if self._profile is not None:
            self._profile.face_tracker_settings.click_threshold_low = float(app_data)

from __future__ import annotations

from typing import Optional

import dearpygui.dearpygui as dpg

from powermouse.domain.models.camera import (
    DEFAULT_TRACKING_ACCELERATION,
    DEFAULT_TRACKING_SPEED,
    FaceTrackerSettings,
)
from powermouse.domain.models.profile import Profile
from powermouse.widgets.style import add_field_label, add_section_heading


class TrackingSettingsWidget:
    """Tracking parameter sliders bound to a FaceTrackerSettings instance (live mutation)."""

    ENABLED_TAG = "tracking_enabled"
    SETTINGS_GROUP_TAG = "tracking_settings_group"
    SPEED_TAG = "tracking_speed"
    ACCEL_TAG = "tracking_accel"
    SENS_X_TAG = "tracking_sens_x"
    SENS_Y_TAG = "tracking_sens_y"
    SMOOTH_TAG = "tracking_smooth"
    DEADZONE_TAG = "tracking_deadzone"
    AREA_X_MIN_TAG = "tracking_area_x_min"
    AREA_X_MAX_TAG = "tracking_area_x_max"
    AREA_Y_MIN_TAG = "tracking_area_y_min"
    AREA_Y_MAX_TAG = "tracking_area_y_max"
    CONTROL_WIDTH = -1

    def __init__(self):
        self._settings: Optional[FaceTrackerSettings] = None
        self._profile: Optional[Profile] = None

    def build(self, parent: str) -> None:
        dpg.add_checkbox(
            label="Face Tracking",
            tag=self.ENABLED_TAG,
            parent=parent,
            default_value=True,
            callback=self._on_enabled,
        )
        # All parameter controls live in one group so disabling tracking
        # greys them out, matching the clicking-interface sections.
        dpg.add_group(tag=self.SETTINGS_GROUP_TAG, parent=parent)
        parent = self.SETTINGS_GROUP_TAG
        add_section_heading(parent, "Motion")
        add_field_label(parent, "Speed")
        dpg.add_slider_float(
            label="", tag=self.SPEED_TAG, parent=parent,
            min_value=0.0, max_value=5.0, default_value=DEFAULT_TRACKING_SPEED,
            width=self.CONTROL_WIDTH,
            callback=self._on_speed,
        )
        add_field_label(parent, "Acceleration")
        dpg.add_slider_float(
            label="", tag=self.ACCEL_TAG, parent=parent,
            min_value=0.1, max_value=5.0, default_value=DEFAULT_TRACKING_ACCELERATION,
            width=self.CONTROL_WIDTH,
            callback=self._on_accel,
        )
        add_field_label(parent, "Sensitivity X")
        dpg.add_slider_float(
            label="", tag=self.SENS_X_TAG, parent=parent,
            min_value=0.0, max_value=5.0, default_value=1.0,
            width=self.CONTROL_WIDTH,
            callback=self._on_sens_x,
        )
        add_field_label(parent, "Sensitivity Y")
        dpg.add_slider_float(
            label="", tag=self.SENS_Y_TAG, parent=parent,
            min_value=0.0, max_value=5.0, default_value=1.0,
            width=self.CONTROL_WIDTH,
            callback=self._on_sens_y,
        )
        add_field_label(parent, "Smoothness")
        dpg.add_slider_float(
            label="", tag=self.SMOOTH_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.5,
            width=self.CONTROL_WIDTH,
            callback=self._on_smooth,
        )
        dpg.add_separator(parent=parent)
        add_section_heading(parent, "Deadzone")
        add_field_label(parent, "Radius (px)")
        dpg.add_slider_int(
            label="", tag=self.DEADZONE_TAG, parent=parent,
            min_value=0, max_value=50, default_value=5,
            width=self.CONTROL_WIDTH,
            callback=self._on_deadzone,
        )
        dpg.add_separator(parent=parent)
        add_section_heading(parent, "Active Area (normalized)")
        add_field_label(parent, "X Min")
        dpg.add_slider_float(
            label="", tag=self.AREA_X_MIN_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.4,
            width=self.CONTROL_WIDTH,
            callback=self._on_area,
        )
        add_field_label(parent, "X Max")
        dpg.add_slider_float(
            label="", tag=self.AREA_X_MAX_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.6,
            width=self.CONTROL_WIDTH,
            callback=self._on_area,
        )
        add_field_label(parent, "Y Min")
        dpg.add_slider_float(
            label="", tag=self.AREA_Y_MIN_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.4,
            width=self.CONTROL_WIDTH,
            callback=self._on_area,
        )
        add_field_label(parent, "Y Max")
        dpg.add_slider_float(
            label="", tag=self.AREA_Y_MAX_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.6,
            width=self.CONTROL_WIDTH,
            callback=self._on_area,
        )

    def bind_profile(self, profile: Profile) -> None:
        """Bind the tracking on/off toggle to a Profile (live mutation)."""
        self._profile = profile
        dpg.set_value(self.ENABLED_TAG, profile.tracking_enabled)
        self._set_settings_enabled(profile.tracking_enabled)

    def bind(self, settings: FaceTrackerSettings) -> None:
        self._settings = settings
        dpg.set_value(self.SPEED_TAG, settings.speed)
        dpg.set_value(self.ACCEL_TAG, settings.acceleration)
        dpg.set_value(self.SENS_X_TAG, settings.sensitivity[0])
        dpg.set_value(self.SENS_Y_TAG, settings.sensitivity[1])
        dpg.set_value(self.SMOOTH_TAG, settings.smoothness)
        dpg.set_value(self.DEADZONE_TAG, settings.deadzone_radius_px)
        dpg.set_value(self.AREA_X_MIN_TAG, settings.active_area_x[0])
        dpg.set_value(self.AREA_X_MAX_TAG, settings.active_area_x[1])
        dpg.set_value(self.AREA_Y_MIN_TAG, settings.active_area_y[0])
        dpg.set_value(self.AREA_Y_MAX_TAG, settings.active_area_y[1])

    # -- callbacks -----------------------------------------------------

    def _set_settings_enabled(self, enabled: bool) -> None:
        if dpg.does_item_exist(self.SETTINGS_GROUP_TAG):
            dpg.configure_item(self.SETTINGS_GROUP_TAG, enabled=enabled)

    def _on_enabled(self, sender, app_data, user_data):  # noqa: ARG002
        enabled = bool(app_data)
        self._set_settings_enabled(enabled)
        if self._profile is not None:
            self._profile.tracking_enabled = enabled

    def _on_speed(self, sender, app_data, user_data):  # noqa: ARG002
        if self._settings is not None:
            self._settings.speed = float(app_data)

    def _on_accel(self, sender, app_data, user_data):  # noqa: ARG002
        if self._settings is not None:
            self._settings.acceleration = float(app_data)

    def _on_sens_x(self, sender, app_data, user_data):  # noqa: ARG002
        if self._settings is not None:
            _, sy = self._settings.sensitivity
            self._settings.sensitivity = (float(app_data), sy)

    def _on_sens_y(self, sender, app_data, user_data):  # noqa: ARG002
        if self._settings is not None:
            sx, _ = self._settings.sensitivity
            self._settings.sensitivity = (sx, float(app_data))

    def _on_smooth(self, sender, app_data, user_data):  # noqa: ARG002
        if self._settings is not None:
            self._settings.smoothness = float(app_data)

    def _on_deadzone(self, sender, app_data, user_data):  # noqa: ARG002
        if self._settings is not None:
            self._settings.deadzone_radius_px = int(app_data)

    def _on_area(self, *_):
        if self._settings is None:
            return
        self._settings.active_area_x = (
            float(dpg.get_value(self.AREA_X_MIN_TAG)),
            float(dpg.get_value(self.AREA_X_MAX_TAG)),
        )
        self._settings.active_area_y = (
            float(dpg.get_value(self.AREA_Y_MIN_TAG)),
            float(dpg.get_value(self.AREA_Y_MAX_TAG)),
        )

from __future__ import annotations

from typing import Optional

import dearpygui.dearpygui as dpg

from powermouse.domain.models.camera import FaceTrackerSettings


class TrackingSettingsWidget:
    """Tracking parameter sliders bound to a FaceTrackerSettings instance (live mutation)."""

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

    def __init__(self):
        self._settings: Optional[FaceTrackerSettings] = None

    def build(self, parent: str) -> None:
        dpg.add_text("Motion", parent=parent)
        dpg.add_slider_float(
            label="Speed", tag=self.SPEED_TAG, parent=parent,
            min_value=0.0, max_value=5.0, default_value=1.0,
            callback=self._on_speed,
        )
        dpg.add_slider_float(
            label="Acceleration", tag=self.ACCEL_TAG, parent=parent,
            min_value=0.1, max_value=5.0, default_value=1.0,
            callback=self._on_accel,
        )
        dpg.add_slider_float(
            label="Sensitivity X", tag=self.SENS_X_TAG, parent=parent,
            min_value=0.0, max_value=5.0, default_value=1.0,
            callback=self._on_sens_x,
        )
        dpg.add_slider_float(
            label="Sensitivity Y", tag=self.SENS_Y_TAG, parent=parent,
            min_value=0.0, max_value=5.0, default_value=1.0,
            callback=self._on_sens_y,
        )
        dpg.add_slider_float(
            label="Smoothness", tag=self.SMOOTH_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.5,
            callback=self._on_smooth,
        )
        dpg.add_separator(parent=parent)
        dpg.add_text("Deadzone", parent=parent)
        dpg.add_slider_int(
            label="Radius (px)", tag=self.DEADZONE_TAG, parent=parent,
            min_value=0, max_value=50, default_value=5,
            callback=self._on_deadzone,
        )
        dpg.add_separator(parent=parent)
        dpg.add_text("Active Area (normalized)", parent=parent)
        dpg.add_slider_float(
            label="X Min", tag=self.AREA_X_MIN_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.4,
            callback=self._on_area,
        )
        dpg.add_slider_float(
            label="X Max", tag=self.AREA_X_MAX_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.6,
            callback=self._on_area,
        )
        dpg.add_slider_float(
            label="Y Min", tag=self.AREA_Y_MIN_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.4,
            callback=self._on_area,
        )
        dpg.add_slider_float(
            label="Y Max", tag=self.AREA_Y_MAX_TAG, parent=parent,
            min_value=0.0, max_value=1.0, default_value=0.6,
            callback=self._on_area,
        )

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

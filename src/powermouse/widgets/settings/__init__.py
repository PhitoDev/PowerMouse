# pyright: reportGeneralTypeIssues=false, reportArgumentType=false
from __future__ import annotations

from typing import Callable, Optional

import dearpygui.dearpygui as dpg

from powermouse.adapters.profile import SqlAlchemyProfileManager
from powermouse.domain.models.camera import Camera
from powermouse.domain.models.mouse import ClickInterface
from powermouse.domain.models.profile import Profile
from powermouse.widgets.style import add_body_text, add_panel_heading

from .clicking import ClickingSettingsWidget
from .tracking import TrackingSettingsWidget


class SettingsWidget:
    """Tabbed detail pane for the selected profile (Tracking | Clicking) + Save/Revert."""

    TAG = "settings_panel"
    TAB_BAR_TAG = "settings_tabs"
    TRACKING_TAB_TAG = "settings_tab_tracking"
    CLICKING_TAB_TAG = "settings_tab_clicking"
    NAME_TAG = "settings_header_name"

    def __init__(
        self,
        profile_manager: SqlAlchemyProfileManager,
        tracking: TrackingSettingsWidget,
        clicking: ClickingSettingsWidget,
        on_saved: Callable[[Profile], None] = lambda _p: None,
    ):
        self._manager = profile_manager
        self._tracking = tracking
        self._clicking = clicking
        self._on_saved = on_saved
        self._current: Optional[Profile] = None
        try:
            self._active_profile: Optional[Profile] = self._manager.get_active_profile()
        except LookupError:
            self._active_profile = None

    def build(self, parent: str) -> None:
        with dpg.child_window(tag=self.TAG, parent=parent, width=-1, border=True):
            add_panel_heading(self.TAG, "Profile Settings")
            add_body_text(self.TAG, "(no profile selected)", tag=self.NAME_TAG)
            with dpg.tab_bar(tag=self.TAB_BAR_TAG):
                dpg.add_tab(label="Tracking", tag=self.TRACKING_TAB_TAG)
                dpg.add_tab(label="Clicking", tag=self.CLICKING_TAB_TAG)
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save", callback=self._save)
                dpg.add_button(label="Revert", callback=self._revert)
        # Populate tabs now that they exist.
        self._tracking.build(parent=self.TRACKING_TAB_TAG)
        self._clicking.build(parent=self.CLICKING_TAB_TAG)

    def bind(self, profile: Profile) -> None:
        self._current = profile
        if profile.is_active:
            self._active_profile = profile
        dpg.set_value(self.NAME_TAG, f"Editing: {profile.name}")
        self._tracking.bind(profile.face_tracker_settings)
        self._clicking.bind(profile)

    def save(self) -> None:
        """Persist the currently selected profile."""
        self._save()

    def revert(self) -> None:
        """Reload the currently selected profile from persisted state."""
        self._revert()

    def select_tracking_tab(self) -> None:
        """Focus the Tracking settings tab."""
        if dpg.does_item_exist(self.TAB_BAR_TAG):
            dpg.set_value(self.TAB_BAR_TAG, self.TRACKING_TAB_TAG)

    def select_clicking_tab(self) -> None:
        """Focus the Clicking settings tab."""
        if dpg.does_item_exist(self.TAB_BAR_TAG):
            dpg.set_value(self.TAB_BAR_TAG, self.CLICKING_TAB_TAG)

    def update_active_profile_camera(self, camera: Camera) -> None:
        """Keep the bound active profile in sync with camera-widget changes."""
        if self._current is not None and self._current.is_active:
            self._current.face_tracker_settings.camera = camera

    def set_active_profile(self, profile: Profile | None) -> None:
        self._active_profile = profile

    def is_gesture_clicking_enabled(self) -> bool:
        if self._current is not None and self._current.is_active:
            return self._current.is_click_interface_enabled(ClickInterface.GESTURE)
        return bool(
            self._active_profile
            and self._active_profile.is_click_interface_enabled(ClickInterface.GESTURE)
        )

    # -- callbacks -----------------------------------------------------

    def _save(self, *_):
        if self._current is None:
            return
        # Camera changes are applied immediately by the camera widget. Preserve
        # the persisted camera here so saving settings cannot overwrite it with
        # a stale in-memory profile copy.
        fresh = self._manager.get_profile(str(self._current.profile_id))
        self._current.face_tracker_settings.camera = fresh.face_tracker_settings.camera
        self._manager.update_profile(self._current.profile_id, self._current)
        if self._current.is_active:
            self._active_profile = self._current
        self._on_saved(self._current)
        self._clicking.apply_runtime()

    def _revert(self, *_):
        if self._current is None:
            return
        fresh = self._manager.get_profile(str(self._current.profile_id))
        # Mutate the current object in place so any external references (e.g., the
        # inference controller) keep pointing at the same instance.
        self._current.name = fresh.name
        self._current.is_active = fresh.is_active
        self._current.click_interfaces = fresh.click_interfaces
        self._current.microphone = fresh.microphone
        fs, fr = self._current.face_tracker_settings, fresh.face_tracker_settings
        fs.speed = fr.speed
        fs.acceleration = fr.acceleration
        fs.sensitivity = fr.sensitivity
        fs.smoothness = fr.smoothness
        fs.deadzone_radius_px = fr.deadzone_radius_px
        fs.active_area_x = fr.active_area_x
        fs.active_area_y = fr.active_area_y
        fs.click_threshold_high = fr.click_threshold_high
        fs.click_threshold_low = fr.click_threshold_low
        if self._current.is_active:
            self._active_profile = self._current
        self.bind(self._current)
        self._clicking.apply_runtime()


__all__ = ["SettingsWidget", "TrackingSettingsWidget", "ClickingSettingsWidget"]

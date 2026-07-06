"""Integration tests for the settings widgets."""
from __future__ import annotations

import dearpygui.dearpygui as dpg
import numpy as np
import pytest

from powermouse.domain.models.camera import Camera
from powermouse.domain.models.mouse import ClickInterface
from powermouse.domain.usecases.gesture_mapping import GESTURE_CLICK_CHEAT_SHEET
from powermouse.widgets.settings import (
    ClickingSettingsWidget,
    SettingsWidget,
    TrackingSettingsWidget,
)


class TestTrackingSettingsWidget:
    def test_bind_populates_slider_values(
        self, dpg_root, face_tracker_settings
    ):
        widget = TrackingSettingsWidget()
        widget.build(dpg_root)
        face_tracker_settings.speed = 2.5
        face_tracker_settings.smoothness = 0.75
        widget.bind(face_tracker_settings)
        assert dpg.get_value(widget.SPEED_TAG) == pytest.approx(2.5)
        assert dpg.get_value(widget.SMOOTH_TAG) == pytest.approx(0.75)

    def test_callback_mutates_bound_settings(
        self, dpg_root, face_tracker_settings
    ):
        widget = TrackingSettingsWidget()
        widget.build(dpg_root)
        widget.bind(face_tracker_settings)
        widget._on_speed(None, 3.5, None)
        widget._on_sens_x(None, 2.0, None)
        widget._on_sens_y(None, 0.25, None)
        widget._on_smooth(None, 0.9, None)
        widget._on_deadzone(None, 12, None)
        assert face_tracker_settings.speed == 3.5
        assert face_tracker_settings.sensitivity == (2.0, 0.25)
        assert face_tracker_settings.smoothness == 0.9
        assert face_tracker_settings.deadzone_radius_px == 12

    def test_active_area_callback_reads_current_slider_values(
        self, dpg_root, face_tracker_settings
    ):
        widget = TrackingSettingsWidget()
        widget.build(dpg_root)
        widget.bind(face_tracker_settings)
        dpg.set_value(widget.AREA_X_MIN_TAG, 0.1)
        dpg.set_value(widget.AREA_X_MAX_TAG, 0.9)
        dpg.set_value(widget.AREA_Y_MIN_TAG, 0.2)
        dpg.set_value(widget.AREA_Y_MAX_TAG, 0.8)
        widget._on_area()
        assert face_tracker_settings.active_area_x == pytest.approx((0.1, 0.9))
        assert face_tracker_settings.active_area_y == pytest.approx((0.2, 0.8))


class TestClickingSettingsWidget:
    def test_bind_populates_checkboxes_and_thresholds(
        self, dpg_root, sample_profile
    ):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)
        sample_profile.face_tracker_settings.click_threshold_high = 0.7
        sample_profile.face_tracker_settings.click_threshold_low = 0.3
        widget.bind(sample_profile)
        assert (
            dpg.get_value(widget._checkbox_tags[ClickInterface.GESTURE]) is True
        )
        assert dpg.get_value(widget.HIGH_TAG) == pytest.approx(0.7)
        assert dpg.get_value(widget.LOW_TAG) == pytest.approx(0.3)

    def test_only_gesture_clicking_checkbox_is_enabled(self, dpg_root):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)

        assert (
            dpg.get_item_configuration(widget._checkbox_tags[ClickInterface.GESTURE])[
                "enabled"
            ]
            is True
        )
        assert (
            dpg.get_item_configuration(widget._checkbox_tags[ClickInterface.DWELL])[
                "enabled"
            ]
            is False
        )
        assert (
            dpg.get_item_configuration(widget._checkbox_tags[ClickInterface.VOICE])[
                "enabled"
            ]
            is False
        )

    def test_toggle_callback_updates_gesture_profile(self, dpg_root, sample_profile):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)
        widget.bind(sample_profile)
        widget._make_on_toggle(ClickInterface.GESTURE)(None, False, None)
        assert not sample_profile.is_click_interface_enabled(ClickInterface.GESTURE)

    def test_disabled_toggle_callback_ignores_unsupported_interfaces(
        self, dpg_root, sample_profile
    ):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)
        widget.bind(sample_profile)
        widget._make_on_toggle(ClickInterface.DWELL)(None, True, None)
        widget._make_on_toggle(ClickInterface.VOICE)(None, True, None)
        assert not sample_profile.is_click_interface_enabled(ClickInterface.DWELL)
        assert not sample_profile.is_click_interface_enabled(ClickInterface.VOICE)

    def test_threshold_callbacks_update_settings(self, dpg_root, sample_profile):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)
        widget.bind(sample_profile)
        widget._on_high(None, 0.85, None)
        widget._on_low(None, 0.15, None)
        assert sample_profile.face_tracker_settings.click_threshold_high == 0.85
        assert sample_profile.face_tracker_settings.click_threshold_low == 0.15

    def test_build_adds_gesture_clicking_cheat_sheet(self, dpg_root):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)

        assert dpg.does_item_exist(widget.CHEAT_SHEET_GROUP_TAG)
        sheet_items = dpg.get_item_children(widget.CHEAT_SHEET_GROUP_TAG, slot=1) or []
        assert len(sheet_items) == len(GESTURE_CLICK_CHEAT_SHEET) * 2


class TestSettingsWidget:
    def test_save_persists_changes(
        self, dpg_root, populated_profile_manager
    ):
        tracking = TrackingSettingsWidget()
        clicking = ClickingSettingsWidget()
        saved: list = []
        widget = SettingsWidget(
            profile_manager=populated_profile_manager,
            tracking=tracking,
            clicking=clicking,
            on_saved=saved.append,
        )
        widget.build(dpg_root)
        profile = populated_profile_manager.list_profiles()[0]
        widget.bind(profile)
        # Mutate via the tracking widget callback.
        tracking._on_speed(None, 4.2, None)
        widget._save()
        # Persisted state must reflect the change.
        reloaded = populated_profile_manager.get_profile(str(profile.profile_id))
        assert reloaded.face_tracker_settings.speed == 4.2
        assert saved == [profile]

    def test_save_preserves_camera_changed_elsewhere(
        self, dpg_root, populated_profile_manager
    ):
        tracking = TrackingSettingsWidget()
        clicking = ClickingSettingsWidget()
        widget = SettingsWidget(
            profile_manager=populated_profile_manager,
            tracking=tracking,
            clicking=clicking,
        )
        widget.build(dpg_root)
        profile = populated_profile_manager.list_profiles()[0]
        widget.bind(profile)

        updated = populated_profile_manager.get_profile(str(profile.profile_id))
        updated.face_tracker_settings.camera = Camera(
            name="Other",
            id="1",
            fps=30.0,
            current_frame=np.zeros((1, 1, 3), dtype=np.uint8),
            frame_width=1,
            frame_height=1,
        )
        populated_profile_manager.update_profile(updated.profile_id, updated)

        tracking._on_speed(None, 4.2, None)
        widget._save()

        reloaded = populated_profile_manager.get_profile(str(profile.profile_id))
        assert reloaded.face_tracker_settings.speed == 4.2
        assert reloaded.face_tracker_settings.camera.id == "1"

    def test_save_persists_disabled_gesture_clicking(
        self, dpg_root, populated_profile_manager
    ):
        tracking = TrackingSettingsWidget()
        clicking = ClickingSettingsWidget()
        widget = SettingsWidget(
            profile_manager=populated_profile_manager,
            tracking=tracking,
            clicking=clicking,
        )
        widget.build(dpg_root)
        profile = populated_profile_manager.list_profiles()[0]
        widget.bind(profile)

        clicking._make_on_toggle(ClickInterface.GESTURE)(None, False, None)
        assert widget.is_gesture_clicking_enabled() is False
        widget._save()

        reloaded = populated_profile_manager.get_profile(str(profile.profile_id))
        assert not reloaded.is_click_interface_enabled(ClickInterface.GESTURE)

    def test_revert_restores_persisted_state(
        self, dpg_root, populated_profile_manager
    ):
        tracking = TrackingSettingsWidget()
        clicking = ClickingSettingsWidget()
        widget = SettingsWidget(
            profile_manager=populated_profile_manager,
            tracking=tracking,
            clicking=clicking,
        )
        widget.build(dpg_root)
        profile = populated_profile_manager.list_profiles()[0]
        original_speed = profile.face_tracker_settings.speed
        widget.bind(profile)
        # Mutate without saving, then revert.
        tracking._on_speed(None, 99.0, None)
        assert profile.face_tracker_settings.speed == 99.0
        widget._revert()
        assert profile.face_tracker_settings.speed == original_speed

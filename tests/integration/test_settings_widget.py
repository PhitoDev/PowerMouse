"""Integration tests for the settings widgets."""
from __future__ import annotations

import copy

import dearpygui.dearpygui as dpg
import numpy as np
import pytest

from powermouse.domain.controllers.voice import MicrophoneManager
from powermouse.domain.models.camera import Camera
from powermouse.domain.models.dwell import PaletteOrientation
from powermouse.domain.models.mouse import ClickInterface
from powermouse.domain.models.microphone import Microphone
from powermouse.domain.usecases.gesture_mapping import GESTURE_CLICK_CHEAT_SHEET
from powermouse.domain.usecases.voice_clicking import (
    CLICK_PHRASES,
    HOLD_PHRASES,
    RELEASE_PHRASES,
)
from powermouse.widgets.settings import (
    ClickingSettingsWidget,
    SettingsWidget,
    TrackingSettingsWidget,
)


class FakeMicrophoneManager(MicrophoneManager):
    def __init__(self, microphones, default=None):
        self.microphones = microphones
        self.default = default

    def get_microphones(self):
        return list(self.microphones)

    def get_default_microphone(self):
        return self.default


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

    def test_bind_profile_populates_tracking_toggle(
        self, dpg_root, sample_profile
    ):
        widget = TrackingSettingsWidget()
        widget.build(dpg_root)
        sample_profile.tracking_enabled = False
        widget.bind_profile(sample_profile)
        assert dpg.get_value(widget.ENABLED_TAG) is False
        assert (
            dpg.get_item_configuration(widget.SETTINGS_GROUP_TAG)["enabled"]
            is False
        )

    def test_enabled_callback_mutates_profile_and_greys_out_sliders(
        self, dpg_root, sample_profile
    ):
        widget = TrackingSettingsWidget()
        widget.build(dpg_root)
        widget.bind_profile(sample_profile)
        widget._on_enabled(None, False, None)
        assert sample_profile.tracking_enabled is False
        assert (
            dpg.get_item_configuration(widget.SETTINGS_GROUP_TAG)["enabled"]
            is False
        )
        widget._on_enabled(None, True, None)
        assert sample_profile.tracking_enabled is True
        assert (
            dpg.get_item_configuration(widget.SETTINGS_GROUP_TAG)["enabled"]
            is True
        )

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

    def test_all_clicking_checkboxes_are_enabled(self, dpg_root):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)

        for interface in (
            ClickInterface.GESTURE,
            ClickInterface.DWELL,
            ClickInterface.VOICE,
        ):
            assert (
                dpg.get_item_configuration(widget._checkbox_tags[interface])[
                    "enabled"
                ]
                is True
            )

    def test_toggle_callback_updates_gesture_profile(self, dpg_root, sample_profile):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)
        widget.bind(sample_profile)
        widget._make_on_toggle(ClickInterface.GESTURE)(None, False, None)
        assert not sample_profile.is_click_interface_enabled(ClickInterface.GESTURE)
        assert (
            dpg.get_item_configuration(widget.GESTURE_SETTINGS_TAG)["enabled"]
            is False
        )

        widget._make_on_toggle(ClickInterface.GESTURE)(None, True, None)
        assert (
            dpg.get_item_configuration(widget.GESTURE_SETTINGS_TAG)["enabled"]
            is True
        )

    def test_dwell_toggle_updates_profile_and_notifies_runtime(
        self, dpg_root, sample_profile
    ):
        applied: list = []
        widget = ClickingSettingsWidget(on_dwell_changed=applied.append)
        widget.build(dpg_root)
        widget.bind(sample_profile)
        widget._make_on_toggle(ClickInterface.DWELL)(None, True, None)
        assert sample_profile.is_click_interface_enabled(ClickInterface.DWELL)
        assert applied == [sample_profile]
        assert (
            dpg.get_item_configuration(widget.DWELL_SETTINGS_TAG)["enabled"] is True
        )

    def test_dwell_setting_callbacks_mutate_profile_and_notify(
        self, dpg_root, sample_profile
    ):
        applied: list = []
        widget = ClickingSettingsWidget(on_dwell_changed=applied.append)
        widget.build(dpg_root)
        widget.bind(sample_profile)
        widget._on_dwell_time(None, 1500, None)
        widget._on_dwell_radius(None, 40, None)
        widget._on_dwell_opacity(None, 0.6, None)
        widget._on_dwell_orientation(None, "Horizontal", None)
        dwell = sample_profile.dwell_settings
        assert dwell.dwell_time_ms == 1500
        assert dwell.radius_px == 40
        assert dwell.palette_opacity == pytest.approx(0.6)
        assert dwell.palette_orientation is PaletteOrientation.HORIZONTAL
        assert len(applied) == 4

    def test_bind_populates_dwell_controls(self, dpg_root, sample_profile):
        sample_profile.dwell_settings.dwell_time_ms = 800
        sample_profile.dwell_settings.palette_orientation = (
            PaletteOrientation.HORIZONTAL
        )
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)
        widget.bind(sample_profile)
        assert dpg.get_value(widget.DWELL_TIME_TAG) == 800
        assert dpg.get_value(widget.DWELL_ORIENTATION_TAG) == "Horizontal"

    def test_threshold_callbacks_update_settings(self, dpg_root, sample_profile):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)
        widget.bind(sample_profile)
        widget._on_high(None, 0.85, None)
        widget._on_low(None, 0.15, None)
        assert sample_profile.face_tracker_settings.click_threshold_high == 0.85
        assert sample_profile.face_tracker_settings.click_threshold_low == 0.15

    def test_build_moves_clicking_instructions_into_info_popups(self, dpg_root):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)

        assert dpg.does_item_exist(widget.CHEAT_SHEET_GROUP_TAG)
        assert dpg.does_item_exist(widget.VOICE_INSTRUCTIONS_TAG)
        sheet_items = dpg.get_item_children(widget.CHEAT_SHEET_GROUP_TAG, slot=1) or []
        assert len(sheet_items) == len(GESTURE_CLICK_CHEAT_SHEET) * 2

    def test_voice_instructions_group_commands_by_action(self, dpg_root):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)

        text_values: list[str] = []

        def collect_text(item) -> None:
            for slot in range(4):
                for child in dpg.get_item_children(item, slot=slot) or []:
                    if dpg.get_item_type(child) == "mvAppItemType::mvText":
                        text_values.append(dpg.get_value(child))
                    collect_text(child)

        collect_text(widget.VOICE_INSTRUCTIONS_TAG)

        assert "Click" in text_values
        assert "Start dragging" in text_values
        assert "Stop dragging" in text_values
        assert "click, left click" in text_values
        assert "hold click, hold left click, start drag, start left drag" in text_values
        assert (
            "release click, release left click, stop drag, stop left drag"
            in text_values
        )
        displayed_phrases = {
            phrase
            for text in text_values
            for phrase in text.split(", ")
            if phrase in {*CLICK_PHRASES, *HOLD_PHRASES, *RELEASE_PHRASES}
        }
        assert displayed_phrases == {
            *CLICK_PHRASES,
            *HOLD_PHRASES,
            *RELEASE_PHRASES,
        }

    def test_bind_enables_only_settings_for_selected_modes(
        self, dpg_root, sample_profile
    ):
        widget = ClickingSettingsWidget()
        widget.build(dpg_root)
        sample_profile.toggle_click_interface(ClickInterface.GESTURE, True)
        sample_profile.toggle_click_interface(ClickInterface.VOICE, False)

        widget.bind(sample_profile)

        assert (
            dpg.get_item_configuration(widget.GESTURE_SETTINGS_TAG)["enabled"]
            is True
        )
        assert (
            dpg.get_item_configuration(widget.VOICE_SETTINGS_TAG)["enabled"]
            is False
        )

    def test_microphone_dropdown_uses_system_default_without_selecting_first(
        self, dpg_root, sample_profile
    ):
        default = Microphone("2", "Default Microphone")
        manager = FakeMicrophoneManager(
            [Microphone("1", "Other Microphone"), default],
            default=default,
        )
        widget = ClickingSettingsWidget(manager)
        widget.build(dpg_root)
        widget.bind(sample_profile)

        assert sample_profile.microphone is None
        assert dpg.get_value(widget.MICROPHONE_TAG).startswith("System default")

    def test_microphone_dropdown_rebinds_changed_index_by_unique_name(
        self, dpg_root, sample_profile
    ):
        sample_profile.microphone = Microphone("8", "USB Microphone")
        manager = FakeMicrophoneManager([Microphone("3", "USB Microphone")])
        widget = ClickingSettingsWidget(manager)
        widget.build(dpg_root)
        widget.bind(sample_profile)

        assert sample_profile.microphone == Microphone("3", "USB Microphone")
        assert dpg.get_value(widget.MICROPHONE_TAG) == "USB Microphone (id: 3)"

    def test_failed_microphone_switch_restores_previous_selection(
        self, dpg_root, sample_profile
    ):
        first = Microphone("1", "First")
        second = Microphone("2", "Second")
        sample_profile.microphone = first
        manager = FakeMicrophoneManager([first, second], default=first)
        widget = ClickingSettingsWidget(
            manager,
            on_voice_changed=lambda _profile: False,
        )
        widget.build(dpg_root)
        widget.bind(sample_profile)

        widget._on_microphone(None, widget._label(second), None)

        assert sample_profile.microphone == first
        assert dpg.get_value(widget.MICROPHONE_TAG) == widget._label(first)


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

    def test_active_click_interface_state_survives_editing_inactive_profile(
        self, dpg_root, populated_profile_manager
    ):
        clicking = ClickingSettingsWidget()
        widget = SettingsWidget(
            profile_manager=populated_profile_manager,
            tracking=TrackingSettingsWidget(),
            clicking=clicking,
        )
        widget.build(dpg_root)
        active = populated_profile_manager.get_active_profile()
        widget.bind(active)
        clicking._make_on_toggle(ClickInterface.GESTURE)(None, False, None)

        inactive = copy.deepcopy(active)
        inactive.profile_id = 0
        inactive.name = "Inactive"
        inactive.is_active = False
        inactive = populated_profile_manager.create_profile(inactive)
        widget.bind(inactive)

        assert widget.is_gesture_clicking_enabled() is False

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

    def test_save_and_revert_include_microphone(
        self, dpg_root, populated_profile_manager
    ):
        microphone = Microphone("3", "USB Microphone")
        clicking = ClickingSettingsWidget(
            FakeMicrophoneManager([microphone], default=microphone)
        )
        widget = SettingsWidget(
            profile_manager=populated_profile_manager,
            tracking=TrackingSettingsWidget(),
            clicking=clicking,
        )
        widget.build(dpg_root)
        profile = populated_profile_manager.get_active_profile()
        widget.bind(profile)

        clicking._on_microphone(None, clicking._label(microphone), None)
        widget._save()
        assert populated_profile_manager.get_active_profile().microphone == microphone

        profile.microphone = None
        widget._revert()
        assert profile.microphone == microphone

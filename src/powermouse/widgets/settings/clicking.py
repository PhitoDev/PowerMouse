from __future__ import annotations

from typing import Callable, Dict, Optional

import dearpygui.dearpygui as dpg

from powermouse.domain.controllers.voice import MicrophoneManager
from powermouse.domain.models.dwell import PaletteOrientation
from powermouse.domain.models.mouse import ClickInterface, MouseButton
from powermouse.domain.models.microphone import Microphone
from powermouse.domain.models.profile import Profile
from powermouse.domain.usecases.voice_clicking import (
    CLICK_PHRASES,
    HOLD_PHRASES,
    RELEASE_PHRASES,
)
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
    GESTURE_SETTINGS_TAG = "clicking_gesture_settings"
    DWELL_SETTINGS_TAG = "clicking_dwell_settings"
    VOICE_SETTINGS_TAG = "clicking_voice_settings"
    CHEAT_SHEET_GROUP_TAG = "clicking_gesture_cheat_sheet"
    VOICE_INSTRUCTIONS_TAG = "clicking_voice_instructions"
    DWELL_TIME_TAG = "clicking_dwell_time"
    DWELL_RADIUS_TAG = "clicking_dwell_radius"
    DWELL_OPACITY_TAG = "clicking_dwell_opacity"
    DWELL_ORIENTATION_TAG = "clicking_dwell_orientation"
    CONTROL_WIDTH = -1
    TOOLTIP_WIDTH = 320
    POPUP_WIDTH = 460
    ENABLED_INTERFACES = {
        ClickInterface.GESTURE,
        ClickInterface.DWELL,
        ClickInterface.VOICE,
    }
    MICROPHONE_TAG = "clicking_microphone"
    STATUS_TAG = "clicking_voice_status"

    DEFAULT_MICROPHONE_LABEL = "System default"
    NO_MICROPHONES_LABEL = "No microphones available"
    CLICK_ACTIONS = (
        ("Left", (MouseButton.LEFT, 1)),
        ("Right", (MouseButton.RIGHT, 1)),
        ("Middle", (MouseButton.MIDDLE, 1)),
        ("Double", (MouseButton.LEFT, 2)),
    )
    DRAG_ACTIONS = (
        ("Left drag", MouseButton.LEFT),
        ("Right drag", MouseButton.RIGHT),
        ("Middle drag", MouseButton.MIDDLE),
    )

    ORIENTATION_LABELS = {
        PaletteOrientation.VERTICAL: "Vertical",
        PaletteOrientation.HORIZONTAL: "Horizontal",
    }

    def __init__(
        self,
        microphone_manager: MicrophoneManager | None = None,
        on_voice_changed: Callable[[Profile], bool] = lambda _p: True,
        on_dwell_changed: Callable[[Profile], None] = lambda _p: None,
    ):
        self._profile: Optional[Profile] = None
        self._microphone_manager = microphone_manager
        self._on_voice_changed = on_voice_changed
        self._on_dwell_changed = on_dwell_changed
        self._microphones: dict[str, Microphone] = {}
        self._microphone_selections: dict[str, Microphone | None] = {}
        self._checkbox_tags: Dict[ClickInterface, str] = {
            ci: f"clicking_interface_{ci.value}" for ci in ClickInterface
        }
        self._settings_tags = {
            ClickInterface.GESTURE: self.GESTURE_SETTINGS_TAG,
            ClickInterface.DWELL: self.DWELL_SETTINGS_TAG,
            ClickInterface.VOICE: self.VOICE_SETTINGS_TAG,
        }

    def build(self, parent: str) -> None:
        gesture_info = self._add_mode_header(parent, ClickInterface.GESTURE)
        with dpg.group(
            tag=self.GESTURE_SETTINGS_TAG,
            parent=parent,
            enabled=False,
        ):
            add_field_label(self.GESTURE_SETTINGS_TAG, "High Threshold")
            dpg.add_slider_float(
                label="", tag=self.HIGH_TAG, parent=self.GESTURE_SETTINGS_TAG,
                min_value=0.0, max_value=1.0, default_value=0.6,
                width=self.CONTROL_WIDTH,
                callback=self._on_high,
            )
            add_field_label(self.GESTURE_SETTINGS_TAG, "Low Threshold")
            dpg.add_slider_float(
                label="", tag=self.LOW_TAG, parent=self.GESTURE_SETTINGS_TAG,
                min_value=0.0, max_value=1.0, default_value=0.4,
                width=self.CONTROL_WIDTH,
                callback=self._on_low,
            )
        with dpg.tooltip(gesture_info):
            tooltip = dpg.last_container()
            dpg.add_spacer(parent=tooltip, width=self.TOOLTIP_WIDTH, height=0)
            add_body_text(
                tooltip,
                "Click for gesture instructions.",
                wrap=self.TOOLTIP_WIDTH,
            )
        with dpg.popup(
            gesture_info,
            mousebutton=dpg.mvMouseButton_Left,
            min_size=(self.POPUP_WIDTH, 100),
            max_size=(self.POPUP_WIDTH, 520),
        ):
            popup = dpg.last_container()
            add_body_text(
                popup,
                "Use these facial gestures while tracking is active:",
                wrap=420,
            )
            add_gesture_cheat_sheet(popup, tag=self.CHEAT_SHEET_GROUP_TAG)

        dpg.add_separator(parent=parent)

        dwell_info = self._add_mode_header(parent, ClickInterface.DWELL)
        with dpg.group(
            tag=self.DWELL_SETTINGS_TAG,
            parent=parent,
            enabled=False,
        ):
            add_field_label(self.DWELL_SETTINGS_TAG, "Dwell Time (ms)")
            dpg.add_slider_int(
                label="", tag=self.DWELL_TIME_TAG, parent=self.DWELL_SETTINGS_TAG,
                min_value=300, max_value=3000, default_value=1000,
                width=self.CONTROL_WIDTH,
                callback=self._on_dwell_time,
            )
            add_field_label(self.DWELL_SETTINGS_TAG, "Movement Radius (px)")
            dpg.add_slider_int(
                label="", tag=self.DWELL_RADIUS_TAG, parent=self.DWELL_SETTINGS_TAG,
                min_value=5, max_value=100, default_value=25,
                width=self.CONTROL_WIDTH,
                callback=self._on_dwell_radius,
            )
            add_field_label(self.DWELL_SETTINGS_TAG, "Palette Opacity")
            dpg.add_slider_float(
                label="", tag=self.DWELL_OPACITY_TAG, parent=self.DWELL_SETTINGS_TAG,
                min_value=0.3, max_value=1.0, default_value=0.85,
                width=self.CONTROL_WIDTH,
                callback=self._on_dwell_opacity,
            )
            add_field_label(self.DWELL_SETTINGS_TAG, "Palette Layout")
            dpg.add_combo(
                list(self.ORIENTATION_LABELS.values()),
                tag=self.DWELL_ORIENTATION_TAG,
                parent=self.DWELL_SETTINGS_TAG,
                default_value=self.ORIENTATION_LABELS[PaletteOrientation.VERTICAL],
                width=self.CONTROL_WIDTH,
                callback=self._on_dwell_orientation,
            )
        with dpg.tooltip(dwell_info):
            tooltip = dpg.last_container()
            dpg.add_spacer(parent=tooltip, width=self.TOOLTIP_WIDTH, height=0)
            add_body_text(
                tooltip,
                "Click for dwell clicking instructions.",
                wrap=self.TOOLTIP_WIDTH,
            )
        with dpg.popup(
            dwell_info,
            mousebutton=dpg.mvMouseButton_Left,
            min_size=(self.POPUP_WIDTH, 100),
            max_size=(self.POPUP_WIDTH, 320),
        ):
            add_body_text(
                dpg.last_container(),
                "Dwell clicking fires the armed action after the pointer rests in "
                "one place for the dwell time. A floating palette lets you arm "
                "Left, Double, Right, Middle, or Drag, pause dwell clicking, and "
                "flip its layout. Rest the pointer on a palette button (or click "
                "it) to activate it; armed actions reset to Left after one click. "
                "Drag the grip at the top of the palette to move it anywhere on "
                "screen.",
                wrap=380,
            )

        dpg.add_separator(parent=parent)

        voice_info = self._add_mode_header(parent, ClickInterface.VOICE)
        with dpg.group(
            tag=self.VOICE_SETTINGS_TAG,
            parent=parent,
            enabled=False,
        ):
            add_field_label(self.VOICE_SETTINGS_TAG, "Microphone")
            dpg.add_combo(
                [],
                tag=self.MICROPHONE_TAG,
                parent=self.VOICE_SETTINGS_TAG,
                width=self.CONTROL_WIDTH,
                callback=self._on_microphone,
            )
            dpg.add_button(
                label="Refresh Microphones",
                parent=self.VOICE_SETTINGS_TAG,
                callback=self._on_refresh,
            )
            add_body_text(self.VOICE_SETTINGS_TAG, "off", tag=self.STATUS_TAG)
        with dpg.tooltip(voice_info):
            tooltip = dpg.last_container()
            dpg.add_spacer(parent=tooltip, width=self.TOOLTIP_WIDTH, height=0)
            add_body_text(
                tooltip,
                "Click for available voice commands.",
                wrap=self.TOOLTIP_WIDTH,
            )
        with dpg.popup(
            voice_info,
            mousebutton=dpg.mvMouseButton_Left,
            min_size=(self.POPUP_WIDTH, 100),
            max_size=(self.POPUP_WIDTH, 360),
        ):
            popup = dpg.last_container()
            add_body_text(
                popup,
                "Say any listed phrase while Voice Clicking is listening.",
                wrap=420,
            )
            with dpg.group(tag=self.VOICE_INSTRUCTIONS_TAG, parent=popup):
                self._add_voice_command_group(
                    self.VOICE_INSTRUCTIONS_TAG,
                    "Click",
                    CLICK_PHRASES,
                    self.CLICK_ACTIONS,
                )
                self._add_voice_command_group(
                    self.VOICE_INSTRUCTIONS_TAG,
                    "Start dragging",
                    HOLD_PHRASES,
                    self.DRAG_ACTIONS,
                )
                self._add_voice_command_group(
                    self.VOICE_INSTRUCTIONS_TAG,
                    "Stop dragging",
                    RELEASE_PHRASES,
                    self.DRAG_ACTIONS,
                )

    @staticmethod
    def _add_voice_command_group(parent, heading, phrases, actions) -> None:
        add_section_heading(parent, heading)
        with dpg.table(
            parent=parent,
            header_row=False,
            borders_innerH=True,
            no_pad_outerX=True,
            policy=dpg.mvTable_SizingStretchProp,
        ) as table:
            dpg.add_table_column(
                parent=table,
                init_width_or_weight=0.34,
                width_stretch=True,
            )
            dpg.add_table_column(
                parent=table,
                init_width_or_weight=0.66,
                width_stretch=True,
            )
            for action, result in actions:
                aliases = [
                    phrase
                    for phrase, mapped_result in phrases.items()
                    if mapped_result == result
                ]
                if not aliases:
                    continue
                with dpg.table_row(parent=table) as row:
                    add_field_label(row, action)
                    add_body_text(row, ", ".join(aliases), wrap=270)

    def _add_mode_header(self, parent: str, ci: ClickInterface) -> int | str:
        with dpg.group(parent=parent, horizontal=True):
            dpg.add_checkbox(
                label=f"{ci.value.title()} Clicking",
                tag=self._checkbox_tags[ci],
                enabled=ci in self.ENABLED_INTERFACES,
                callback=self._make_on_toggle(ci),
            )
            return dpg.add_button(label="?", small=True)

    def bind(self, profile: Profile) -> None:
        self._profile = profile
        self.refresh_microphones()
        for ci, tag in self._checkbox_tags.items():
            enabled = profile.is_click_interface_enabled(ci)
            dpg.set_value(tag, enabled)
            self._set_settings_enabled(ci, enabled)
        dpg.set_value(self.HIGH_TAG, profile.face_tracker_settings.click_threshold_high)
        dpg.set_value(self.LOW_TAG, profile.face_tracker_settings.click_threshold_low)
        dwell = profile.dwell_settings
        dpg.set_value(self.DWELL_TIME_TAG, dwell.dwell_time_ms)
        dpg.set_value(self.DWELL_RADIUS_TAG, dwell.radius_px)
        dpg.set_value(self.DWELL_OPACITY_TAG, dwell.palette_opacity)
        dpg.set_value(
            self.DWELL_ORIENTATION_TAG,
            self.ORIENTATION_LABELS[dwell.palette_orientation],
        )

    def refresh_microphones(self) -> None:
        manager = self._microphone_manager
        try:
            microphones = manager.get_microphones() if manager else []
            default = manager.get_default_microphone() if manager else None
        except Exception as exc:
            microphones = []
            default = None
            self.set_status(f"microphone discovery failed: {exc}")

        self._microphones = {m.id: m for m in microphones}
        self._microphone_selections = {}

        labels: list[str] = []
        if default is not None:
            default_label = f"{self.DEFAULT_MICROPHONE_LABEL} — {self._label(default)}"
            labels.append(default_label)
            self._microphone_selections[default_label] = None
        labels.extend(self._label(microphone) for microphone in microphones)
        self._microphone_selections.update(
            (self._label(microphone), microphone) for microphone in microphones
        )

        profile = self._profile
        selected = profile.microphone if profile else None
        selected_label = self.NO_MICROPHONES_LABEL
        if selected is None and default is not None:
            selected_label = default_label
        elif selected is not None and manager is not None:
            resolved = manager.resolve_microphone(selected)
            if resolved is not None:
                # Refresh the persisted identity on the next Save when the
                # device name uniquely matches but PortAudio changed its index.
                profile.microphone = resolved
                selected_label = self._label(resolved)
            else:
                selected_label = self._label(selected, unavailable=True)
                labels.append(selected_label)

        if not labels:
            labels = [self.NO_MICROPHONES_LABEL]
        dpg.configure_item(self.MICROPHONE_TAG, items=labels)
        dpg.set_value(self.MICROPHONE_TAG, selected_label)

    @staticmethod
    def _label(microphone: Microphone | None, unavailable: bool = False) -> str:
        if microphone is None:
            return "No microphones"
        label = f"{microphone.name} (id: {microphone.id})"
        return f"{label} — unavailable" if unavailable else label

    # -- callbacks -----------------------------------------------------

    def _make_on_toggle(self, ci: ClickInterface):
        def cb(sender, app_data, user_data):  # noqa: ARG001
            if ci not in self.ENABLED_INTERFACES:
                return
            enabled = bool(app_data)
            self._set_settings_enabled(ci, enabled)
            if self._profile is not None:
                self._profile.toggle_click_interface(ci, enabled)
                if ci is ClickInterface.VOICE:
                    self._on_voice_changed(self._profile)
                elif ci is ClickInterface.DWELL:
                    self._on_dwell_changed(self._profile)
        return cb

    def _set_settings_enabled(self, ci: ClickInterface, enabled: bool) -> None:
        tag = self._settings_tags.get(ci)
        if tag is not None and dpg.does_item_exist(tag):
            dpg.configure_item(tag, enabled=enabled)

    def _on_refresh(self, *_):
        self.refresh_microphones()

    def _on_microphone(self, sender, app_data, user_data):  # noqa: ARG002
        if self._profile is None:
            return
        if app_data not in self._microphone_selections:
            return

        previous = self._profile.microphone
        chosen = self._microphone_selections[app_data]
        self._profile.microphone = chosen
        if self._on_voice_changed(self._profile):
            return

        self._profile.microphone = previous
        if previous is None:
            default_label = next(
                (
                    label
                    for label, microphone in self._microphone_selections.items()
                    if microphone is None
                ),
                self.NO_MICROPHONES_LABEL,
            )
            dpg.set_value(self.MICROPHONE_TAG, default_label)
        else:
            resolved = (
                self._microphone_manager.resolve_microphone(previous)
                if self._microphone_manager
                else None
            )
            dpg.set_value(
                self.MICROPHONE_TAG,
                self._label(resolved or previous, unavailable=resolved is None),
            )

    def set_status(self, status: str) -> None:
        if dpg.does_item_exist(self.STATUS_TAG):
            dpg.set_value(self.STATUS_TAG, status)

    def apply_runtime(self) -> None:
        if self._profile is not None:
            self._on_voice_changed(self._profile)
            self._on_dwell_changed(self._profile)

    def _on_high(self, sender, app_data, user_data):  # noqa: ARG002
        if self._profile is not None:
            self._profile.face_tracker_settings.click_threshold_high = float(app_data)

    def _on_low(self, sender, app_data, user_data):  # noqa: ARG002
        if self._profile is not None:
            self._profile.face_tracker_settings.click_threshold_low = float(app_data)

    def _dwell_changed(self) -> None:
        if self._profile is not None:
            self._on_dwell_changed(self._profile)

    def _on_dwell_time(self, sender, app_data, user_data):  # noqa: ARG002
        if self._profile is not None:
            self._profile.dwell_settings.dwell_time_ms = int(app_data)
            self._dwell_changed()

    def _on_dwell_radius(self, sender, app_data, user_data):  # noqa: ARG002
        if self._profile is not None:
            self._profile.dwell_settings.radius_px = int(app_data)
            self._dwell_changed()

    def _on_dwell_opacity(self, sender, app_data, user_data):  # noqa: ARG002
        if self._profile is not None:
            self._profile.dwell_settings.palette_opacity = float(app_data)
            self._dwell_changed()

    def _on_dwell_orientation(self, sender, app_data, user_data):  # noqa: ARG002
        if self._profile is None:
            return
        for orientation, label in self.ORIENTATION_LABELS.items():
            if label == app_data:
                self._profile.dwell_settings.palette_orientation = orientation
                self._dwell_changed()
                return

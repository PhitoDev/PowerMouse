# pyright: reportGeneralTypeIssues=false, reportArgumentType=false
from __future__ import annotations

import copy
from typing import Callable, Dict, Optional

import dearpygui.dearpygui as dpg

from powermouse.adapters.profile import SqlAlchemyProfileManager
from powermouse.domain.models.profile import Profile
from powermouse.widgets.style import add_panel_heading, add_section_heading


class ProfilesWidget:
    """Selectable list of profiles with new/delete/set-active controls."""

    TAG = "profiles_panel"
    LIST_TAG = "profiles_list"

    def __init__(
        self,
        profile_manager: SqlAlchemyProfileManager,
        on_selection_changed: Callable[[Profile], None],
    ):
        self._manager = profile_manager
        self._on_selection_changed = on_selection_changed
        self._profiles: Dict[int, Profile] = {}
        self._selected_id: Optional[int] = None

    # -- lifecycle -----------------------------------------------------

    def build(self, parent: str) -> None:
        with dpg.child_window(tag=self.TAG, parent=parent, width=240, border=True):
            add_panel_heading(self.TAG, "Profiles")
            dpg.add_group(tag=self.LIST_TAG)
            dpg.add_spacer(height=8)
            dpg.add_separator()
            add_section_heading(self.TAG, "Actions")
            dpg.add_button(label="New Profile", width=-1, callback=self._on_new)
            dpg.add_button(label="Set Active", width=-1, callback=self._on_set_active)
            dpg.add_button(label="Delete", width=-1, callback=self._on_delete)
        self._reload_list()

    def select_initial(self) -> None:
        """Trigger the initial selection callback. Call after all widgets are built."""
        if self._selected_id is not None:
            return
        if not self._profiles:
            return
        active = next((p for p in self._profiles.values() if p.is_active), None)
        target = active or next(iter(self._profiles.values()))
        self._select(target.profile_id)

    # -- helpers -------------------------------------------------------

    @property
    def current(self) -> Optional[Profile]:
        if self._selected_id is None:
            return None
        return self._profiles.get(self._selected_id)

    def new_profile(self) -> None:
        """Duplicate the selected profile."""
        self._on_new()

    def delete_selected(self) -> None:
        """Delete the selected profile."""
        self._on_delete()

    def set_active_selected(self) -> None:
        """Make the selected profile active."""
        self._on_set_active()

    def _reload_list(self) -> None:
        """Re-read profiles from DB, preserving in-memory edits for ids that still exist."""
        db_profiles = self._manager.list_profiles()
        db_ids = {p.profile_id for p in db_profiles}

        # Drop profiles that no longer exist.
        for pid in list(self._profiles.keys()):
            if pid not in db_ids:
                del self._profiles[pid]

        # Insert any new profiles.
        for p in db_profiles:
            if p.profile_id not in self._profiles:
                self._profiles[p.profile_id] = p

        self._rebuild_list_items()

    def _rebuild_list_items(self) -> None:
        if dpg.does_item_exist(self.LIST_TAG):
            dpg.delete_item(self.LIST_TAG, children_only=True)
        # Keep a deterministic order.
        for pid in sorted(self._profiles):
            profile = self._profiles[pid]
            label = f"{(chr(9733) + ' ') if profile.is_active else '   '}{profile.name}"
            tag = self._select_tag(pid)
            dpg.add_selectable(
                label=label,
                tag=tag,
                parent=self.LIST_TAG,
                default_value=(pid == self._selected_id),
                callback=self._make_on_click(pid),
            )

    @staticmethod
    def _select_tag(profile_id: int) -> str:
        return f"profile_select_{profile_id}"

    def _make_on_click(self, profile_id: int):
        def cb(sender, app_data, user_data):  # noqa: ARG001
            self._select(profile_id)
        return cb

    def _select(self, profile_id: int) -> None:
        profile = self._profiles.get(profile_id)
        if profile is None:
            return
        # Radio-like behavior: clear other selectables.
        for pid in self._profiles:
            tag = self._select_tag(pid)
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, pid == profile_id)
        self._selected_id = profile_id
        self._on_selection_changed(profile)

    # -- button callbacks ---------------------------------------------

    def _on_new(self, *_):
        template = self.current
        if template is None:
            return
        new_profile = copy.deepcopy(template)
        new_profile.profile_id = 0
        new_profile.name = f"{template.name} (copy)"
        new_profile.is_active = False
        created = self._manager.create_profile(new_profile)
        self._profiles[created.profile_id] = created
        self._rebuild_list_items()
        self._select(created.profile_id)

    def _on_delete(self, *_):
        if self._selected_id is None:
            return
        pid = self._selected_id
        self._manager.delete_profile(pid)
        self._profiles.pop(pid, None)
        self._selected_id = None
        self._rebuild_list_items()
        # Pick a fallback selection.
        if self._profiles:
            self._select(next(iter(sorted(self._profiles))))

    def _on_set_active(self, *_):
        profile = self.current
        if profile is None:
            return
        # Toggle flags in-memory; the manager enforces the single-active invariant on save.
        for p in self._profiles.values():
            p.is_active = (p.profile_id == profile.profile_id)
        self._manager.update_profile(profile.profile_id, profile)
        self._rebuild_list_items()

"""Integration tests for ``powermouse.widgets.profiles.ProfilesWidget``.

The widget owns a real :class:`SqlAlchemyProfileManager` (in-memory) so we
exercise the persistence + UI-state interaction together.
"""
from __future__ import annotations

import dearpygui.dearpygui as dpg

from powermouse.widgets.profiles import ProfilesWidget


def _make_widget(manager, sink):
    return ProfilesWidget(profile_manager=manager, on_selection_changed=sink.append)


class TestProfilesWidget:
    def test_select_initial_picks_active_profile(
        self, dpg_root, populated_profile_manager
    ):
        sink: list = []
        widget = _make_widget(populated_profile_manager, sink)
        widget.build(dpg_root)
        widget.select_initial()
        assert widget.current is not None
        assert widget.current.is_active is True
        assert sink and sink[-1] is widget.current

    def test_new_profile_duplicates_current(
        self, dpg_root, populated_profile_manager
    ):
        sink: list = []
        widget = _make_widget(populated_profile_manager, sink)
        widget.build(dpg_root)
        widget.select_initial()
        widget._on_new()

        profiles = populated_profile_manager.list_profiles()
        assert len(profiles) == 2
        copied = next(p for p in profiles if p.name.endswith("(copy)"))
        # Copy must not be active and the widget should now select it.
        assert copied.is_active is False
        assert widget.current is not None
        assert widget.current.profile_id == copied.profile_id

    def test_set_active_persists_and_reloads(
        self, dpg_root, populated_profile_manager, sample_profile
    ):
        sink: list = []
        widget = _make_widget(populated_profile_manager, sink)
        widget.build(dpg_root)
        widget.select_initial()
        widget._on_new()  # create copy, currently selected

        widget._on_set_active()
        active = populated_profile_manager.get_active_profile()
        assert active.profile_id == widget.current.profile_id
        # The other profile should now be inactive.
        others = [
            p
            for p in populated_profile_manager.list_profiles()
            if p.profile_id != active.profile_id
        ]
        assert all(not p.is_active for p in others)

    def test_delete_removes_profile_and_falls_back(
        self, dpg_root, populated_profile_manager
    ):
        sink: list = []
        widget = _make_widget(populated_profile_manager, sink)
        widget.build(dpg_root)
        widget.select_initial()
        widget._on_new()  # second profile, selected
        delete_id = widget.current.profile_id

        widget._on_delete()
        remaining_ids = {
            p.profile_id for p in populated_profile_manager.list_profiles()
        }
        assert delete_id not in remaining_ids
        # After delete with profiles remaining, selection falls back.
        assert widget.current is not None
        assert widget.current.profile_id in remaining_ids

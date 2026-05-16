"""Integration tests for the first-run :class:`OnboardingDialog`.

We cannot run the DearPyGui main loop in CI, but the dialog is split such
that ``_build``, ``_refresh_cameras`` and ``_on_create`` can be exercised
against a headless DPG context.
"""
from __future__ import annotations

import dearpygui.dearpygui as dpg
import pytest

from powermouse.widgets.onboarding import OnboardingDialog


@pytest.fixture
def dialog(profile_manager, fake_device_manager):
    dpg.create_context()
    dlg = OnboardingDialog(profile_manager, fake_device_manager)
    try:
        dlg._build()
        yield dlg
    finally:
        try:
            dpg.destroy_context()
        except Exception:
            pass


class TestOnboardingDialog:
    def test_refresh_cameras_populates_combo(self, dialog, camera):
        dialog._refresh_cameras()
        items = dpg.get_item_configuration(dialog.CAMERA_TAG)["items"]
        assert items == [f"{camera.name} (id={camera.id})"]
        # Create button should now be enabled.
        assert dpg.get_item_configuration(dialog.CREATE_TAG)["enabled"] is True

    def test_refresh_cameras_handles_empty_list(self, profile_manager):
        from tests.conftest import FakeDeviceManager

        dpg.create_context()
        try:
            d = OnboardingDialog(profile_manager, FakeDeviceManager([]))
            d._build()
            d._refresh_cameras()
            assert dpg.get_value(d.CAMERA_TAG) == "No cameras detected"
            assert dpg.get_item_configuration(d.CREATE_TAG)["enabled"] is False
        finally:
            try:
                dpg.destroy_context()
            except Exception:
                pass

    def test_on_create_requires_name(self, dialog, profile_manager):
        dialog._refresh_cameras()
        dpg.set_value(dialog.NAME_TAG, "   ")
        dialog._on_create()
        assert dialog._created is None
        assert dpg.get_value(dialog.STATUS_TAG) == "Profile name is required."
        assert profile_manager.list_profiles() == []

    def test_on_create_persists_profile(self, dialog, profile_manager, camera):
        dialog._refresh_cameras()
        dpg.set_value(dialog.NAME_TAG, "MyProfile")
        dialog._on_create()
        assert dialog._created is not None
        assert dialog._created.name == "MyProfile"
        assert dialog._created.is_active is True
        # Profile is reachable via the manager and has the expected camera.
        persisted = profile_manager.list_profiles()
        assert len(persisted) == 1
        assert persisted[0].name == "MyProfile"
        assert persisted[0].face_tracker_settings.camera.id == camera.id

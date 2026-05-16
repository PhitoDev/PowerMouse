"""Integration-test fixtures that boot a headless DearPyGui context per test.

DearPyGui can build a widget tree without a viewport; ``set_value`` /
``get_value`` round-trips work, so callbacks can be exercised by directly
invoking them with the stored values.
"""
from __future__ import annotations

import dearpygui.dearpygui as dpg
import pytest


@pytest.fixture
def dpg_root():
    """Create a fresh DPG context with a parent window and tear it down."""
    dpg.create_context()
    try:
        with dpg.window(tag="test_root"):
            pass
        yield "test_root"
    finally:
        try:
            dpg.destroy_context()
        except Exception:
            pass

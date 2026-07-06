# pyright: reportGeneralTypeIssues=false, reportArgumentType=false
"""Application-wide theme: Lakers palette + JetBrains Mono Nerd Font.

Call :func:`setup_theme` once *after* ``dpg.create_context()`` to install the
global font and color theme. Subsequent calls (e.g. onboarding -> main window)
reuse the cached font registration.
"""

from __future__ import annotations

import os
from typing import Optional

import dearpygui.dearpygui as dpg

# -- assets --------------------------------------------------------------

FONT_PATH = os.path.join(
    os.path.dirname(__file__), "../resources/JetBrainsMonoNerdFont-ExtraBold.ttf"
)
assert os.path.exists(FONT_PATH), f"Font file not found: {FONT_PATH}"

FONT_SIZE = 25
BODY_FONT_SIZE = 21
SECTION_FONT_SIZE = 27

# -- Lakers palette ------------------------------------------------------

LAKERS_PURPLE = (85, 37, 131, 255)  # #552583
LAKERS_GOLD = (253, 185, 39, 255)  # #FDB927
LAKERS_GOLD_SOFT = (253, 185, 39, 160)  # translucent for hovers
OFF_WHITE = (250, 247, 242, 255)  # #FAF7F2
OFF_WHITE_DEEP = (238, 233, 224, 255)  # slightly darker for frame bgs
STATUS_RED = (170, 40, 40, 255)  # readable on off-white

# -- module state --------------------------------------------------------

_font_id: Optional[int] = None
_font_ids: dict[tuple[str, int], int] = {}
_theme_id: Optional[int] = None


def load_font(path: str = FONT_PATH, size: int = FONT_SIZE) -> int:
    """Register (or return cached) global font id."""
    global _font_id, _font_ids
    key = (path, size)
    font_id = _font_ids.get(key)
    if font_id is not None and dpg.does_item_exist(font_id):
        return font_id
    with dpg.font_registry():
        font_id = dpg.add_font(path, size)
    _font_ids[key] = font_id
    if path == FONT_PATH and size == FONT_SIZE:
        _font_id = font_id
    return font_id


def apply_theme() -> None:
    """Build and bind the global Lakers theme."""
    global _theme_id
    if _theme_id is None or not dpg.does_item_exist(_theme_id):
        with dpg.theme() as _theme_id:
            with dpg.theme_component(dpg.mvAll):
                # Backgrounds -> Lakers purple
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_PopupBg, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_MenuBarBg, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgCollapsed, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_TableHeaderBg, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_TableRowBg, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_TableRowBgAlt, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, LAKERS_PURPLE)

                # Text -> off-white
                dpg.add_theme_color(dpg.mvThemeCol_Text, OFF_WHITE)
                dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, OFF_WHITE_DEEP)

                # Borders, separators, accents, highlights -> Lakers gold
                dpg.add_theme_color(dpg.mvThemeCol_Border, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_BorderShadow, LAKERS_GOLD_SOFT)
                dpg.add_theme_color(dpg.mvThemeCol_Separator, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_SeparatorHovered, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_SeparatorActive, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_TableBorderStrong, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_TableBorderLight, LAKERS_GOLD_SOFT)

                dpg.add_theme_color(dpg.mvThemeCol_Button, LAKERS_GOLD_SOFT)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, LAKERS_GOLD)

                dpg.add_theme_color(dpg.mvThemeCol_Header, LAKERS_GOLD_SOFT)
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, LAKERS_GOLD)

                dpg.add_theme_color(dpg.mvThemeCol_Tab, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_TabHovered, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_TabActive, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_TabUnfocused, LAKERS_PURPLE)
                dpg.add_theme_color(dpg.mvThemeCol_TabUnfocusedActive, LAKERS_GOLD_SOFT)

                dpg.add_theme_color(dpg.mvThemeCol_CheckMark, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_ResizeGrip, LAKERS_GOLD_SOFT)
                dpg.add_theme_color(dpg.mvThemeCol_ResizeGripHovered, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_ResizeGripActive, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, LAKERS_GOLD_SOFT)
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_PlotHistogram, LAKERS_GOLD)
                dpg.add_theme_color(dpg.mvThemeCol_PlotHistogramHovered, LAKERS_GOLD)

                # Style: make borders visible
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_PopupBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_TabBorderSize, 1)

    dpg.bind_theme(_theme_id)


def setup_theme() -> int:
    """Load the font + apply the theme. Returns the font id."""
    font_id = load_font()
    dpg.bind_font(font_id)
    apply_theme()
    return font_id

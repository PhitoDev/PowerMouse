# pyright: reportGeneralTypeIssues=false, reportArgumentType=false
"""Small DearPyGui styling helpers shared by application widgets."""
from __future__ import annotations

import dearpygui.dearpygui as dpg

from powermouse.domain.usecases.gesture_mapping import GESTURE_CLICK_CHEAT_SHEET
from powermouse.theme import (
    BODY_FONT_SIZE,
    LAKERS_GOLD,
    OFF_WHITE,
    OFF_WHITE_DEEP,
    SECTION_FONT_SIZE,
    STATUS_RED,
    load_font,
)


def add_panel_heading(parent: str | int, text: str) -> int | str:
    heading = dpg.add_text(text, parent=parent, color=LAKERS_GOLD)
    dpg.bind_item_font(heading, load_font(size=SECTION_FONT_SIZE))
    dpg.add_separator(parent=parent)
    return heading


def add_section_heading(parent: str | int, text: str) -> int | str:
    heading = dpg.add_text(text, parent=parent, color=LAKERS_GOLD)
    dpg.bind_item_font(heading, load_font(size=SECTION_FONT_SIZE))
    dpg.add_separator(parent=parent)
    return heading


def add_alert_heading(parent: str | int, text: str, *, tag: str | int = 0) -> int | str:
    heading = dpg.add_text(text, tag=tag, parent=parent, color=STATUS_RED)
    dpg.bind_item_font(heading, load_font(size=SECTION_FONT_SIZE))
    dpg.add_separator(parent=parent)
    return heading


def add_field_label(parent: str | int, text: str) -> int | str:
    label = dpg.add_text(text, parent=parent, color=OFF_WHITE)
    dpg.bind_item_font(label, load_font(size=BODY_FONT_SIZE))
    return label


def add_body_text(
    parent: str | int,
    text: str,
    *,
    tag: str | int = 0,
    wrap: int = 0,
    color: tuple[int, int, int, int] = OFF_WHITE_DEEP,
) -> int | str:
    body = dpg.add_text(text, tag=tag, parent=parent, wrap=wrap, color=color)
    dpg.bind_item_font(body, load_font(size=BODY_FONT_SIZE))
    return body


def add_gesture_cheat_sheet(parent: str | int, *, tag: str | int = 0) -> int | str:
    with dpg.group(tag=tag, parent=parent) as group:
        for gesture, action in GESTURE_CLICK_CHEAT_SHEET:
            gesture_text = dpg.add_text(
                gesture,
                parent=group,
                bullet=True,
                color=LAKERS_GOLD,
                wrap=0,
            )
            action_text = dpg.add_text(
                action,
                parent=group,
                indent=24,
                color=OFF_WHITE_DEEP,
                wrap=0,
            )
            dpg.bind_item_font(gesture_text, load_font(size=BODY_FONT_SIZE))
            dpg.bind_item_font(action_text, load_font(size=BODY_FONT_SIZE))
    return group

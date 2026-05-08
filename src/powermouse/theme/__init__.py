"""Theme package. ``global.py`` cannot be imported with the normal ``from
powermouse.theme.global import ...`` syntax because ``global`` is a Python
keyword, so we load it via :mod:`importlib` and re-export its public API."""

from importlib import import_module as _import_module

_mod = _import_module("powermouse.theme.global")

FONT_PATH = _mod.FONT_PATH
FONT_SIZE = _mod.FONT_SIZE
LAKERS_PURPLE = _mod.LAKERS_PURPLE
LAKERS_GOLD = _mod.LAKERS_GOLD
LAKERS_GOLD_SOFT = _mod.LAKERS_GOLD_SOFT
OFF_WHITE = _mod.OFF_WHITE
OFF_WHITE_DEEP = _mod.OFF_WHITE_DEEP
STATUS_RED = _mod.STATUS_RED
apply_theme = _mod.apply_theme
load_font = _mod.load_font
setup_theme = _mod.setup_theme

__all__ = [
    "FONT_PATH",
    "FONT_SIZE",
    "LAKERS_PURPLE",
    "LAKERS_GOLD",
    "LAKERS_GOLD_SOFT",
    "OFF_WHITE",
    "OFF_WHITE_DEEP",
    "STATUS_RED",
    "apply_theme",
    "load_font",
    "setup_theme",
]

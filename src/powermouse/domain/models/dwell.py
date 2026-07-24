from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DwellAction(Enum):
    """Actions exposed on the floating dwell palette."""

    LEFT = "left"
    DOUBLE = "double"
    RIGHT = "right"
    MIDDLE = "middle"
    DRAG_TOGGLE = "drag_toggle"
    PAUSE = "pause"
    FLIP_LAYOUT = "flip_layout"
    #: The grip/handle region: dwelling on it picks the palette up so it
    #: follows the cursor; the next dwell anywhere drops it.
    MOVE = "move"


#: Palette actions that arm the next on-screen dwell (one-shot).
ARMABLE_ACTIONS = (
    DwellAction.LEFT,
    DwellAction.DOUBLE,
    DwellAction.RIGHT,
    DwellAction.MIDDLE,
    DwellAction.DRAG_TOGGLE,
)


class PaletteOrientation(Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"

    def flipped(self) -> "PaletteOrientation":
        if self is PaletteOrientation.VERTICAL:
            return PaletteOrientation.HORIZONTAL
        return PaletteOrientation.VERTICAL


DEFAULT_DWELL_TIME_MS = 1000
DEFAULT_DWELL_RADIUS_PX = 25
DEFAULT_PALETTE_OPACITY = 0.85


@dataclass
class DwellSettings:
    dwell_time_ms: int = DEFAULT_DWELL_TIME_MS
    radius_px: int = DEFAULT_DWELL_RADIUS_PX
    palette_opacity: float = DEFAULT_PALETTE_OPACITY
    palette_orientation: PaletteOrientation = PaletteOrientation.VERTICAL

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

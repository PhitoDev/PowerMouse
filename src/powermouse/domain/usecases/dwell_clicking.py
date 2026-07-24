"""Dwell-clicking state machine.

Pure policy fed ``(cursor, timestamp_ms)`` once per tracking frame; returns
``MouseEvent`` lists for the caller to dispatch. Click ownership is shared
with gesture/voice via :class:`MouseActionCoordinator` (owner
``ClickInterface.DWELL``).

Behavior (see the dwell-clicking design thread):

- The cursor resting within ``radius_px`` for ``dwell_time_ms`` fires a dwell.
- Over the palette, a completed dwell activates the hovered button (arming an
  action, toggling drag, pausing, or flipping the layout) and never sends an
  OS click; the palette is display-only.
- Dwelling on the palette grip (``DwellAction.MOVE``) picks the palette up:
  it follows the cursor until the next completed dwell drops it. No OS events
  fire while moving.
- Anywhere else, a completed dwell fires the armed action one-shot, then the
  armed action reverts to LEFT.
- While the DWELL owner is holding a drag, any on-screen dwell releases it.
- After firing, the cursor must escape the dwell radius before a new dwell
  can start (no repeat-clicking while resting).
"""
from __future__ import annotations

from powermouse.domain.controllers.dwell_palette import DwellPaletteController
from powermouse.domain.controllers.mouse import MouseController
from powermouse.domain.models.dwell import (
    ARMABLE_ACTIONS,
    DwellAction,
    DwellSettings,
)
from powermouse.domain.models.mouse import ClickInterface, MouseButton, MouseEvent
from powermouse.domain.usecases.mouse_actions import MouseActionCoordinator

#: Report palette progress only when it moves at least this much (limits IPC).
_PROGRESS_STEP = 0.05


class DwellClicker:
    def __init__(
        self,
        settings: DwellSettings,
        palette: DwellPaletteController | None = None,
        coordinator: MouseActionCoordinator | None = None,
    ) -> None:
        self.settings = settings
        self.palette = palette
        self.coordinator = coordinator or MouseActionCoordinator()
        self.armed: DwellAction = DwellAction.LEFT
        self.paused = False
        #: True while the palette has been picked up and follows the cursor.
        self.moving = False
        self._anchor: tuple[int, int] | None = None
        self._anchor_ts = 0
        self._cooldown = False
        self._reported_progress = 0.0

    # -- public API ------------------------------------------------------

    def step(self, cursor: tuple[int, int], timestamp_ms: int) -> list[MouseEvent]:
        events: list[MouseEvent] = []

        # Buttons activated by real clicks on the palette window behave the
        # same as dwell-activated ones.
        if self.palette is not None:
            for action in self.palette.poll_activations():
                events.extend(self._activate(action, cursor))

        # Picked up: the palette tracks the cursor until a dwell drops it.
        if self.moving and self.palette is not None:
            self.palette.follow(cursor[0], cursor[1])

        if self._anchor is None or not self._within_radius(cursor, self._anchor):
            # Cursor escaped: start (or restart) timing from here.
            self._anchor = cursor
            self._anchor_ts = timestamp_ms
            self._cooldown = False
            self._report_progress(None, 0.0)
            return events

        if self._cooldown:
            return events

        hovered = (
            self.palette.hovered_action(cursor[0], cursor[1])
            if self.palette is not None
            else None
        )
        in_palette = self.palette is not None and self.palette.contains(
            cursor[0], cursor[1]
        )

        elapsed = timestamp_ms - self._anchor_ts
        fraction = min(1.0, elapsed / max(1, self.settings.dwell_time_ms))
        holding = self.coordinator.is_owned(ClickInterface.DWELL, MouseButton.LEFT)
        # Show progress except for suppressed dwells (paused with nothing to
        # activate, or hovering palette chrome).
        if self.moving:
            self._report_progress(DwellAction.MOVE, fraction)
        elif hovered is not None or (not in_palette and (not self.paused or holding)):
            self._report_progress(hovered, fraction)
        else:
            self._report_progress(None, 0.0)

        if elapsed < self.settings.dwell_time_ms:
            return events

        self._cooldown = True
        self._report_progress(None, 0.0)
        if self.moving:
            # Drop the palette here. Works even while paused, and takes
            # priority over everything else so the user can't get stuck
            # carrying the palette around.
            self.moving = False
        elif in_palette:
            if hovered is not None:
                events.extend(self._activate(hovered, cursor))
        elif holding:
            # A drag is in progress: any on-screen dwell drops it here, even
            # while paused (never leave the user stuck holding a button).
            events.extend(self._release_drag(cursor))
        elif not self.paused:
            events.extend(self._fire_screen(cursor))
        return events

    def reset(self) -> None:
        """Forget timing state (e.g. when dwell clicking is disabled)."""
        self._anchor = None
        self._cooldown = False
        self.moving = False
        self._report_progress(None, 0.0)

    def reset_holds(self, cursor: tuple[int, int]) -> list[MouseEvent]:
        """Release any dwell-owned holds. Call when dwell clicking stops."""
        events = self.coordinator.release_all(ClickInterface.DWELL, cursor)
        if self.palette is not None:
            self.palette.set_drag_active(False)
        return events

    # -- internals ---------------------------------------------------------

    def _within_radius(self, a: tuple[int, int], b: tuple[int, int]) -> bool:
        radius = self.settings.radius_px
        dx, dy = a[0] - b[0], a[1] - b[1]
        return dx * dx + dy * dy <= radius * radius

    def _report_progress(self, action: DwellAction | None, fraction: float) -> None:
        if self.palette is None:
            return
        if fraction in (0.0, 1.0) or abs(fraction - self._reported_progress) >= _PROGRESS_STEP:
            self._reported_progress = fraction
            self.palette.set_progress(action, fraction)

    def _set_armed(self, action: DwellAction) -> None:
        self.armed = action
        if self.palette is not None:
            self.palette.set_armed(action)

    def _activate(self, action: DwellAction, cursor: tuple[int, int]) -> list[MouseEvent]:
        if action in ARMABLE_ACTIONS:
            if action is DwellAction.DRAG_TOGGLE and self.coordinator.is_owned(
                ClickInterface.DWELL, MouseButton.LEFT
            ):
                # Toggling drag off from the palette releases immediately.
                return self._release_drag(cursor)
            self._set_armed(action)
            return []
        if action is DwellAction.PAUSE:
            self.paused = not self.paused
            if self.palette is not None:
                self.palette.set_paused(self.paused)
            return []
        if action is DwellAction.FLIP_LAYOUT:
            self.settings.palette_orientation = self.settings.palette_orientation.flipped()
            if self.palette is not None:
                self.palette.apply_settings(self.settings)
            return []
        if action is DwellAction.MOVE:
            self.moving = True
            return []
        return []

    def _release_drag(self, cursor: tuple[int, int]) -> list[MouseEvent]:
        events = self.coordinator.release(
            ClickInterface.DWELL, MouseButton.LEFT, cursor
        )
        if self.palette is not None:
            self.palette.set_drag_active(False)
        return events

    def _fire_screen(self, cursor: tuple[int, int]) -> list[MouseEvent]:
        armed = self.armed
        self._set_armed(DwellAction.LEFT)  # one-shot: revert after firing
        match armed:
            case DwellAction.LEFT:
                return self.coordinator.click(MouseButton.LEFT, cursor)
            case DwellAction.DOUBLE:
                return self.coordinator.click(MouseButton.LEFT, cursor, 2)
            case DwellAction.RIGHT:
                return self.coordinator.click(MouseButton.RIGHT, cursor)
            case DwellAction.MIDDLE:
                return self.coordinator.click(MouseButton.MIDDLE, cursor)
            case DwellAction.DRAG_TOGGLE:
                events = self.coordinator.acquire(
                    ClickInterface.DWELL, MouseButton.LEFT, cursor
                )
                if events and self.palette is not None:
                    self.palette.set_drag_active(True)
                return events
            case _:
                return []


def dwell_clicking_step(
    clicker: DwellClicker,
    mouse_controller: MouseController,
    cursor: tuple[int, int],
    timestamp_ms: int,
    enabled: bool,
    was_active: bool,
) -> bool:
    """Advance dwell clicking for one dispatch tick.

    Runs independently of the camera pipeline: the caller supplies the cursor
    position (the real OS cursor). Returns the new ``was_active`` flag. On the
    tick after dwell is disabled, the clicker is reset and any dwell-owned
    drag is released exactly once.
    """
    if not enabled:
        if was_active:
            clicker.reset()
            for event in clicker.reset_holds(cursor):
                mouse_controller.handle_event(event)
        return False
    for event in clicker.step(cursor, timestamp_ms):
        mouse_controller.handle_event(event)
    return True

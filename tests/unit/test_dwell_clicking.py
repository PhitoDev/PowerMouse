"""Unit tests for ``powermouse.domain.usecases.dwell_clicking``."""
from __future__ import annotations

from powermouse.domain.controllers.dwell_palette import DwellPaletteController
from powermouse.domain.models.dwell import (
    DwellAction,
    DwellSettings,
    PaletteOrientation,
)
from powermouse.domain.models.mouse import ClickInterface, MouseButton, MouseEventType
from powermouse.domain.usecases.dwell_clicking import DwellClicker, dwell_clicking_step
from powermouse.domain.usecases.gesture_mapping import GestureToMouseTranslator
from powermouse.domain.usecases.mouse_actions import MouseActionCoordinator
from powermouse.domain.models.gesture import GestureEvent


def kinds(events):
    return [(event.button, event.event_type) for event in events]


CLICK_PAIR = [
    (MouseButton.LEFT, MouseEventType.BUTTON_DOWN),
    (MouseButton.LEFT, MouseEventType.BUTTON_UP),
]


class FakePalette(DwellPaletteController):
    """Palette double with scriptable geometry and recorded outputs."""

    def __init__(self):
        self.bounds: tuple[int, int, int, int] | None = None  # x, y, w, h
        self.buttons: dict[DwellAction, tuple[int, int, int, int]] = {}
        self.activations: list[DwellAction] = []
        self.armed: list[DwellAction] = []
        self.drag_active: list[bool] = []
        self.paused: list[bool] = []
        self.progress: list[tuple[DwellAction | None, float]] = []
        self.applied_settings: list[DwellSettings] = []
        self.followed: list[tuple[int, int]] = []
        self.shown = False

    def show(self):
        self.shown = True

    def hide(self):
        self.shown = False

    def apply_settings(self, settings):
        self.applied_settings.append(settings)

    def set_armed(self, action):
        self.armed.append(action)

    def set_drag_active(self, active):
        self.drag_active.append(active)

    def set_paused(self, paused):
        self.paused.append(paused)

    def set_progress(self, action, fraction):
        self.progress.append((action, fraction))

    def follow(self, x, y):
        self.followed.append((x, y))

    def contains(self, x, y):
        if self.bounds is None:
            return False
        bx, by, bw, bh = self.bounds
        return bx <= x < bx + bw and by <= y < by + bh

    def hovered_action(self, x, y):
        for action, (bx, by, bw, bh) in self.buttons.items():
            if bx <= x < bx + bw and by <= y < by + bh:
                return action
        return None

    def poll_activations(self):
        drained, self.activations = self.activations, []
        return drained


def make_clicker(palette=None, coordinator=None, **settings_overrides):
    settings = DwellSettings(**settings_overrides)
    return DwellClicker(settings, palette=palette, coordinator=coordinator)


def run_dwell(clicker, cursor, start_ms=0, dwell_ms=None):
    """Feed a settled cursor through a full dwell; return all emitted events."""
    dwell_ms = dwell_ms if dwell_ms is not None else clicker.settings.dwell_time_ms
    events = []
    events.extend(clicker.step(cursor, start_ms))
    events.extend(clicker.step(cursor, start_ms + dwell_ms // 2))
    events.extend(clicker.step(cursor, start_ms + dwell_ms))
    return events


class TestScreenDwell:
    def test_fires_left_click_after_dwell_time(self):
        clicker = make_clicker(dwell_time_ms=1000)
        assert clicker.step((100, 100), 0) == []
        assert clicker.step((100, 100), 500) == []
        assert kinds(clicker.step((100, 100), 1000)) == CLICK_PAIR

    def test_small_jitter_within_radius_still_fires(self):
        clicker = make_clicker(dwell_time_ms=1000, radius_px=25)
        assert clicker.step((100, 100), 0) == []
        assert clicker.step((110, 95), 500) == []
        assert kinds(clicker.step((95, 108), 1000)) == CLICK_PAIR

    def test_escape_resets_the_timer(self):
        clicker = make_clicker(dwell_time_ms=1000, radius_px=25)
        assert clicker.step((100, 100), 0) == []
        # Escaped: timing restarts from the new anchor.
        assert clicker.step((200, 200), 900) == []
        assert clicker.step((200, 200), 1500) == []
        assert kinds(clicker.step((200, 200), 1900)) == CLICK_PAIR

    def test_cooldown_blocks_repeat_clicks_until_escape(self):
        clicker = make_clicker(dwell_time_ms=1000)
        run_dwell(clicker, (100, 100))
        # Still resting: nothing fires, no matter how long.
        assert clicker.step((100, 100), 5000) == []
        assert clicker.step((101, 101), 9000) == []
        # Escape then settle again: a new dwell can fire.
        assert clicker.step((300, 300), 10000) == []
        assert kinds(clicker.step((300, 300), 11000)) == CLICK_PAIR

    def test_respects_coordinator_ownership(self):
        coordinator = MouseActionCoordinator()
        gesture = GestureToMouseTranslator(coordinator)
        gesture.translate(GestureEvent.OPEN_MOUTH, (0, 0))  # gesture holds LEFT
        clicker = make_clicker(coordinator=coordinator)
        assert run_dwell(clicker, (100, 100)) == []


class TestPaletteDwell:
    def make(self, **overrides):
        palette = FakePalette()
        palette.bounds = (1000, 0, 200, 400)
        palette.buttons = {
            DwellAction.RIGHT: (1010, 10, 180, 40),
            DwellAction.DRAG_TOGGLE: (1010, 60, 180, 40),
            DwellAction.PAUSE: (1010, 110, 180, 40),
            DwellAction.FLIP_LAYOUT: (1010, 160, 180, 40),
        }
        return make_clicker(palette=palette, **overrides), palette

    def test_dwell_on_button_arms_without_os_click(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        assert run_dwell(clicker, (1020, 20)) == []
        assert clicker.armed is DwellAction.RIGHT
        assert palette.armed[-1] is DwellAction.RIGHT

    def test_armed_action_fires_once_then_reverts_to_left(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        run_dwell(clicker, (1020, 20))  # arm RIGHT
        events = run_dwell(clicker, (300, 300), start_ms=2000)
        assert kinds(events) == [
            (MouseButton.RIGHT, MouseEventType.BUTTON_DOWN),
            (MouseButton.RIGHT, MouseEventType.BUTTON_UP),
        ]
        assert clicker.armed is DwellAction.LEFT
        assert palette.armed[-1] is DwellAction.LEFT
        # Next dwell is a plain left click.
        assert kinds(run_dwell(clicker, (500, 500), start_ms=4000)) == CLICK_PAIR

    def test_dwell_on_palette_chrome_does_nothing(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        # Inside bounds but not over any button.
        assert run_dwell(clicker, (1020, 350)) == []
        assert clicker.armed is DwellAction.LEFT
        assert palette.armed == []

    def test_drag_toggle_presses_then_screen_dwell_releases(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        run_dwell(clicker, (1020, 70))  # arm DRAG_TOGGLE
        assert clicker.armed is DwellAction.DRAG_TOGGLE
        press = run_dwell(clicker, (300, 300), start_ms=2000)
        assert kinds(press) == [(MouseButton.LEFT, MouseEventType.BUTTON_DOWN)]
        assert palette.drag_active[-1] is True
        # Armed reverted, but while holding, the next screen dwell releases.
        assert clicker.armed is DwellAction.LEFT
        release = run_dwell(clicker, (400, 400), start_ms=4000)
        assert kinds(release) == [(MouseButton.LEFT, MouseEventType.BUTTON_UP)]
        assert palette.drag_active[-1] is False

    def test_drag_toggle_on_palette_releases_active_hold(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        run_dwell(clicker, (1020, 70))  # arm DRAG_TOGGLE
        run_dwell(clicker, (300, 300), start_ms=2000)  # press
        release = run_dwell(clicker, (1020, 70), start_ms=4000)
        assert kinds(release) == [(MouseButton.LEFT, MouseEventType.BUTTON_UP)]
        assert palette.drag_active[-1] is False

    def test_pause_suppresses_screen_dwells_but_not_palette(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        run_dwell(clicker, (1020, 120))  # PAUSE
        assert clicker.paused is True
        assert palette.paused[-1] is True
        assert run_dwell(clicker, (300, 300), start_ms=2000) == []
        # Palette still responds: unpause.
        run_dwell(clicker, (1020, 120), start_ms=4000)
        assert clicker.paused is False
        assert kinds(run_dwell(clicker, (300, 300), start_ms=6000)) == CLICK_PAIR

    def test_pause_still_releases_an_active_drag(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        run_dwell(clicker, (1020, 70))  # arm DRAG_TOGGLE
        run_dwell(clicker, (300, 300), start_ms=2000)  # press
        run_dwell(clicker, (1020, 120), start_ms=4000)  # PAUSE
        release = run_dwell(clicker, (400, 400), start_ms=6000)
        assert kinds(release) == [(MouseButton.LEFT, MouseEventType.BUTTON_UP)]

    def test_flip_layout_updates_settings_and_palette(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        run_dwell(clicker, (1020, 170))
        assert clicker.settings.palette_orientation is PaletteOrientation.HORIZONTAL
        assert palette.applied_settings[-1] is clicker.settings

    def test_real_click_activations_are_applied(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        palette.activations.append(DwellAction.MIDDLE)
        assert clicker.step((300, 300), 0) == []
        assert clicker.armed is DwellAction.MIDDLE

    def test_progress_is_reported_while_timing(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        clicker.step((300, 300), 0)
        clicker.step((300, 300), 500)
        assert (None, 0.5) in palette.progress


class TestPaletteMove:
    """Dwell on the grip picks the palette up; the next dwell drops it."""

    def make(self, **overrides):
        palette = FakePalette()
        palette.bounds = (1000, 0, 200, 400)
        palette.buttons = {DwellAction.MOVE: (1000, 0, 200, 30)}
        return make_clicker(palette=palette, **overrides), palette

    def test_dwell_on_grip_starts_move_without_os_events(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        assert run_dwell(clicker, (1100, 15)) == []
        assert clicker.moving is True

    def test_palette_follows_cursor_while_moving(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        run_dwell(clicker, (1100, 15))
        clicker.step((500, 500), 2000)
        clicker.step((600, 550), 2100)
        assert palette.followed == [(500, 500), (600, 550)]

    def test_dwell_drops_the_palette_without_clicking(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        run_dwell(clicker, (1100, 15))
        # Escape the pickup anchor, then dwell to drop: no OS events fire
        # even though the cursor is outside the palette.
        assert run_dwell(clicker, (500, 500), start_ms=2000) == []
        assert clicker.moving is False
        follow_count = len(palette.followed)
        clicker.step((500, 500), 4000)
        assert len(palette.followed) == follow_count

    def test_screen_dwell_after_drop_clicks_normally(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        run_dwell(clicker, (1100, 15))  # pick up
        run_dwell(clicker, (500, 500), start_ms=2000)  # drop
        assert kinds(run_dwell(clicker, (300, 300), start_ms=4000)) == CLICK_PAIR

    def test_drop_works_while_paused(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        clicker.paused = True
        run_dwell(clicker, (1100, 15))  # pick up (palette works while paused)
        assert clicker.moving is True
        assert run_dwell(clicker, (500, 500), start_ms=2000) == []
        assert clicker.moving is False
        # Still paused: the next screen dwell must not click.
        assert run_dwell(clicker, (300, 300), start_ms=4000) == []

    def test_move_progress_is_reported_while_carrying(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        run_dwell(clicker, (1100, 15))
        clicker.step((500, 500), 2000)
        clicker.step((500, 500), 2500)
        assert (DwellAction.MOVE, 0.5) in palette.progress

    def test_reset_cancels_move_mode(self):
        clicker, palette = self.make(dwell_time_ms=1000)
        run_dwell(clicker, (1100, 15))
        clicker.reset()
        assert clicker.moving is False
        clicker.step((500, 500), 2000)
        assert palette.followed == []


class TestDwellClickingStep:
    """The per-tick entry point used by the dispatch loop (camera-free)."""

    def test_enabled_dispatches_dwell_events(self, recording_mouse_controller):
        clicker = make_clicker(dwell_time_ms=1000)
        active = False
        for ts in (0, 500, 1000):
            active = dwell_clicking_step(
                clicker, recording_mouse_controller, (100, 100), ts, True, active
            )
        assert active is True
        assert kinds(recording_mouse_controller.events) == CLICK_PAIR

    def test_disabled_releases_drag_exactly_once(self, recording_mouse_controller):
        palette = FakePalette()
        palette.bounds = (1000, 0, 200, 400)
        palette.buttons = {DwellAction.DRAG_TOGGLE: (1010, 60, 180, 40)}
        clicker = make_clicker(palette=palette, dwell_time_ms=1000)
        run_dwell(clicker, (1020, 70))  # arm DRAG_TOGGLE
        run_dwell(clicker, (300, 300), start_ms=2000)  # press (drag active)

        active = dwell_clicking_step(
            clicker, recording_mouse_controller, (300, 300), 4000, False, True
        )
        assert active is False
        assert kinds(recording_mouse_controller.events) == [
            (MouseButton.LEFT, MouseEventType.BUTTON_UP)
        ]
        # Subsequent disabled ticks are no-ops.
        active = dwell_clicking_step(
            clicker, recording_mouse_controller, (300, 300), 4100, False, active
        )
        assert active is False
        assert len(recording_mouse_controller.events) == 1

    def test_disabled_without_prior_activity_is_a_noop(
        self, recording_mouse_controller
    ):
        clicker = make_clicker()
        active = dwell_clicking_step(
            clicker, recording_mouse_controller, (0, 0), 0, False, False
        )
        assert active is False
        assert recording_mouse_controller.events == []


class TestResets:
    def test_reset_holds_releases_dwell_owned_buttons_only(self):
        coordinator = MouseActionCoordinator()
        gesture = GestureToMouseTranslator(coordinator)
        clicker = make_clicker(coordinator=coordinator)
        gesture.translate(GestureEvent.OPEN_MOUTH, (0, 0))  # gesture holds LEFT
        assert clicker.reset_holds((0, 0)) == []
        assert coordinator.is_owned(ClickInterface.GESTURE, MouseButton.LEFT)

    def test_reset_holds_releases_active_drag(self):
        palette = FakePalette()
        palette.bounds = (1000, 0, 200, 400)
        palette.buttons = {DwellAction.DRAG_TOGGLE: (1010, 60, 180, 40)}
        clicker = make_clicker(palette=palette, dwell_time_ms=1000)
        run_dwell(clicker, (1020, 70))
        run_dwell(clicker, (300, 300), start_ms=2000)  # press
        assert kinds(clicker.reset_holds((300, 300))) == [
            (MouseButton.LEFT, MouseEventType.BUTTON_UP)
        ]
        assert palette.drag_active[-1] is False

    def test_reset_forgets_timing_state(self):
        clicker = make_clicker(dwell_time_ms=1000)
        clicker.step((100, 100), 0)
        clicker.reset()
        # Timer restarted: firing needs a full dwell from the reset point.
        assert clicker.step((100, 100), 900) == []
        assert clicker.step((100, 100), 1500) == []
        assert kinds(clicker.step((100, 100), 1900)) == CLICK_PAIR

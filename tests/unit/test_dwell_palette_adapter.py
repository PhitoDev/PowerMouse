"""Unit tests for the subprocess-backed dwell palette adapter.

Uses a fake child process over real OS pipes so the JSON-lines protocol is
exercised without Tk or a display.
"""
from __future__ import annotations

import json
import os
import time

import pytest

from powermouse.adapters.dwell_palette import PaletteGeometry, SubprocessDwellPalette
from powermouse.domain.models.dwell import (
    DwellAction,
    DwellSettings,
    PaletteOrientation,
)


class TestPaletteGeometry:
    LAYOUT = {
        "event": "layout",
        "bounds": [100, 200, 80, 300],
        "buttons": {
            "left": [106, 220, 68, 30],
            "right": [106, 260, 68, 30],
            "bogus_action": [0, 0, 10, 10],
        },
    }

    def test_contains_and_hover(self):
        geometry = PaletteGeometry()
        geometry.update(self.LAYOUT)
        assert geometry.contains(120, 230)
        assert not geometry.contains(50, 50)
        assert geometry.hovered_action(120, 230) is DwellAction.LEFT
        assert geometry.hovered_action(120, 270) is DwellAction.RIGHT
        # Inside bounds but on chrome (grip/padding): no button.
        assert geometry.hovered_action(101, 201) is None

    def test_unknown_actions_are_ignored(self):
        geometry = PaletteGeometry()
        geometry.update(self.LAYOUT)
        assert DwellAction.LEFT in geometry.buttons
        assert len(geometry.buttons) == 2

    def test_clear(self):
        geometry = PaletteGeometry()
        geometry.update(self.LAYOUT)
        geometry.clear()
        assert not geometry.contains(120, 230)
        assert geometry.hovered_action(120, 230) is None


class FakePaletteProcess:
    """Stands in for the Tk palette child: real pipes, no Tk."""

    def __init__(self):
        stdin_read, stdin_write = os.pipe()
        stdout_read, stdout_write = os.pipe()
        # The adapter writes commands to .stdin and reads events from .stdout.
        self.stdin = os.fdopen(stdin_write, "w")
        self.stdout = os.fdopen(stdout_read, "r")
        # The "child" side, driven by the test.
        self._commands = os.fdopen(stdin_read, "r")
        self._events = os.fdopen(stdout_write, "w")
        self._returncode: int | None = None

    # subprocess.Popen surface used by the adapter --------------------------

    def poll(self):
        return self._returncode

    def wait(self, timeout=None):
        return self._returncode if self._returncode is not None else 0

    def terminate(self):
        self.die()

    # test helpers -----------------------------------------------------------

    def emit(self, message: dict) -> None:
        self._events.write(json.dumps(message) + "\n")
        self._events.flush()

    def sent_commands(self) -> list[dict]:
        """Drain commands written by the adapter so far.

        Closes the adapter-side stdin first so the read hits EOF instead of
        blocking; only call once the adapter is done writing.
        """
        try:
            self.stdin.close()
        except OSError:
            pass
        return [json.loads(line) for line in self._commands if line.strip()]

    def die(self) -> None:
        self._returncode = 1
        for stream in (self._commands, self._events, self.stdin, self.stdout):
            try:
                stream.close()
            except OSError:
                pass


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def fake_process():
    process = FakePaletteProcess()
    yield process
    process.die()


def make_palette(fake_process) -> SubprocessDwellPalette:
    return SubprocessDwellPalette(spawn=lambda: fake_process)


class TestSubprocessDwellPalette:
    def test_no_spawn_until_shown(self, fake_process):
        spawned = []

        def spawn():
            spawned.append(True)
            return fake_process

        palette = SubprocessDwellPalette(spawn=spawn)
        palette.apply_settings(DwellSettings())
        palette.set_armed(DwellAction.RIGHT)
        assert spawned == []
        palette.show()
        assert spawned == [True]

    def test_show_replays_state_to_child(self, fake_process):
        palette = make_palette(fake_process)
        settings = DwellSettings(
            palette_opacity=0.5,
            palette_orientation=PaletteOrientation.HORIZONTAL,
        )
        palette.apply_settings(settings)
        palette.set_armed(DwellAction.DOUBLE)
        palette.show()
        palette.stop()

        commands = fake_process.sent_commands()
        ops = [c["op"] for c in commands]
        assert "config" in ops and "armed" in ops and "show" in ops
        config = next(c for c in commands if c["op"] == "config")
        assert config["opacity"] == 0.5
        assert config["orientation"] == "horizontal"
        armed = next(c for c in commands if c["op"] == "armed")
        assert armed["action"] == "double"

    def test_layout_events_drive_hit_testing(self, fake_process):
        palette = make_palette(fake_process)
        palette.show()
        fake_process.emit(
            {
                "event": "layout",
                "bounds": [10, 10, 100, 100],
                "buttons": {"pause": [20, 20, 40, 20]},
            }
        )
        assert wait_until(lambda: palette.contains(50, 50))
        assert palette.hovered_action(30, 30) is DwellAction.PAUSE
        assert palette.hovered_action(90, 90) is None

    def test_activations_are_queued_and_drained(self, fake_process):
        palette = make_palette(fake_process)
        palette.show()
        fake_process.emit({"event": "activate", "action": "right"})
        fake_process.emit({"event": "activate", "action": "not_a_real_action"})
        fake_process.emit({"event": "activate", "action": "pause"})

        seen: list[DwellAction] = []

        def collected():
            seen.extend(palette.poll_activations())
            return len(seen) >= 2

        assert wait_until(collected)
        assert seen == [DwellAction.RIGHT, DwellAction.PAUSE]
        assert palette.poll_activations() == []

    def test_follow_sends_position_and_is_not_replayed(self, fake_process):
        palette = make_palette(fake_process)
        palette.show()
        palette.follow(640, 400)
        palette.stop()
        commands = fake_process.sent_commands()
        follows = [c for c in commands if c["op"] == "follow"]
        assert follows == [{"op": "follow", "x": 640, "y": 400}]

    def test_move_region_is_hit_testable(self, fake_process):
        palette = make_palette(fake_process)
        palette.show()
        fake_process.emit(
            {
                "event": "layout",
                "bounds": [10, 10, 100, 200],
                "buttons": {
                    "flip_layout": [80, 12, 25, 20],
                    "move": [10, 10, 100, 25],
                },
            }
        )
        assert wait_until(lambda: palette.contains(50, 50))
        # Flip wins its own rect (emitted first); the rest of the grip is move.
        assert palette.hovered_action(90, 20) is DwellAction.FLIP_LAYOUT
        assert palette.hovered_action(30, 20) is DwellAction.MOVE

    def test_hide_clears_geometry(self, fake_process):
        palette = make_palette(fake_process)
        palette.show()
        fake_process.emit(
            {"event": "layout", "bounds": [0, 0, 50, 50], "buttons": {}}
        )
        assert wait_until(lambda: palette.contains(10, 10))
        palette.hide()
        assert not palette.contains(10, 10)

    def test_dead_child_never_raises(self, fake_process):
        palette = make_palette(fake_process)
        palette.show()
        fake_process.die()
        # Writes after child death must not raise; geometry must clear.
        palette.set_armed(DwellAction.LEFT)
        palette.set_progress(None, 0.5)
        assert wait_until(lambda: not palette.contains(0, 0))
        palette.stop()

    def test_spawn_failure_is_swallowed(self):
        def spawn():
            raise OSError("no interpreter")

        palette = SubprocessDwellPalette(spawn=spawn)
        palette.show()  # must not raise
        assert palette.poll_activations() == []
        assert not palette.contains(0, 0)
        palette.stop()

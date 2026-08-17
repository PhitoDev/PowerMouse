"""Subprocess-backed implementation of the dwell-palette port.

Spawns ``python -m powermouse.palette`` (a Tk overlay; Tk needs its own main
thread, which Dear PyGui already owns in this process) and speaks JSON lines
over its stdin/stdout. See ``powermouse.palette.__main__`` for the protocol.

Thread safety: public methods may be called from both the UI thread
(profile changes) and the mouse-dispatch worker (per-frame dwell steps), so
writes are serialized with a lock. Geometry updates arrive on a reader
thread and are swapped in atomically.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from typing import Callable

from powermouse.domain.controllers.dwell_palette import DwellPaletteController
from powermouse.domain.models.dwell import DwellAction, DwellSettings


class PaletteGeometry:
    """Pure hit-testing state built from ``layout`` events."""

    def __init__(self) -> None:
        self.bounds: tuple[int, int, int, int] | None = None
        self.buttons: dict[DwellAction, tuple[int, int, int, int]] = {}

    def update(self, message: dict) -> None:
        bounds = message.get("bounds")
        if isinstance(bounds, list) and len(bounds) == 4:
            self.bounds = tuple(int(v) for v in bounds)
        buttons: dict[DwellAction, tuple[int, int, int, int]] = {}
        for name, rect in (message.get("buttons") or {}).items():
            try:
                action = DwellAction(name)
            except ValueError:
                continue
            if isinstance(rect, list) and len(rect) == 4:
                buttons[action] = tuple(int(v) for v in rect)
        self.buttons = buttons

    def clear(self) -> None:
        self.bounds = None
        self.buttons = {}

    @staticmethod
    def _hit(rect: tuple[int, int, int, int], x: int, y: int) -> bool:
        rx, ry, rw, rh = rect
        return rx <= x < rx + rw and ry <= y < ry + rh

    def contains(self, x: int, y: int) -> bool:
        return self.bounds is not None and self._hit(self.bounds, x, y)

    def hovered_action(self, x: int, y: int) -> DwellAction | None:
        for action, rect in self.buttons.items():
            if self._hit(rect, x, y):
                return action
        return None


def _default_spawn() -> subprocess.Popen:
    # From source, ``sys.executable`` is a real Python interpreter and ``-m``
    # runs the palette module directly. In a Briefcase-packaged app it is the
    # app's stub binary, which ignores ``-m`` and always reruns
    # ``powermouse.__main__`` -- without the env var below that would open
    # another main window (recursively). ``powermouse/__main__.py`` checks
    # POWERMOUSE_PALETTE and dispatches to the palette instead.
    return subprocess.Popen(
        [sys.executable, "-m", "powermouse.palette"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env={**os.environ, "POWERMOUSE_PALETTE": "1"},
    )


# A palette process that dies this quickly after spawning is considered
# broken (e.g. tkinter missing from a packaged app) rather than crashed.
_RAPID_EXIT_WINDOW_S = 5.0
# After this many consecutive rapid exits, stop respawning for the rest of
# the session instead of burning CPU on a spawn loop.
_MAX_RAPID_EXITS = 3


class SubprocessDwellPalette(DwellPaletteController):
    def __init__(self, spawn: Callable[[], subprocess.Popen] = _default_spawn):
        self._spawn = spawn
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._geometry = PaletteGeometry()
        self._activations: queue.SimpleQueue[DwellAction] = queue.SimpleQueue()
        self._visible = False
        # Last state, replayed after a (re)spawn so a crashed palette comes
        # back looking the way it did.
        self._replay: dict[str, dict] = {}
        self._spawned_at = 0.0
        self._rapid_exits = 0
        self._disabled = False

    # -- process lifecycle -------------------------------------------------

    def _alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _ensure_process_locked(self) -> bool:
        if self._alive():
            return True
        if self._disabled:
            return False
        if time.monotonic() - self._spawned_at < _RAPID_EXIT_WINDOW_S:
            self._rapid_exits += 1
            if self._rapid_exits >= _MAX_RAPID_EXITS:
                self._disabled = True
                return False
        else:
            self._rapid_exits = 0
        self._geometry.clear()
        try:
            self._process = self._spawn()
        except OSError:
            self._process = None
            return False
        self._spawned_at = time.monotonic()
        threading.Thread(
            target=self._read_events,
            args=(self._process,),
            name="dwell-palette-reader",
            daemon=True,
        ).start()
        for message in self._replay.values():
            self._write_locked(message)
        return True

    def _read_events(self, process: subprocess.Popen) -> None:
        stdout = process.stdout
        if stdout is None:
            return
        try:
            for line in stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if message.get("event") == "layout":
                    self._geometry.update(message)
                elif message.get("event") == "activate":
                    try:
                        self._activations.put(DwellAction(message.get("action")))
                    except ValueError:
                        continue
        except (OSError, ValueError):
            pass  # Stream closed mid-read; treat like EOF.
        # EOF: the palette process died or was closed. Without a window there
        # is nothing to hit-test against.
        self._geometry.clear()

    def _write_locked(self, message: dict) -> None:
        process = self._process
        if process is None or process.stdin is None:
            return
        try:
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            self._process = None
            self._geometry.clear()

    def _send(self, message: dict, replay_key: str | None = None) -> None:
        with self._lock:
            if replay_key is not None:
                self._replay[replay_key] = message
            if not self._visible and message.get("op") not in ("hide", "quit"):
                # Do not keep a process around for an invisible palette; the
                # replay cache restores state on the next show().
                if not self._alive():
                    return
            elif not self._ensure_process_locked():
                return
            self._write_locked(message)

    # -- DwellPaletteController --------------------------------------------

    def show(self) -> None:
        with self._lock:
            self._visible = True
            self._replay["show"] = {"op": "show"}
            if self._ensure_process_locked():
                self._write_locked({"op": "show"})

    def hide(self) -> None:
        with self._lock:
            self._visible = False
            self._replay.pop("show", None)
            self._geometry.clear()
            if self._alive():
                self._write_locked({"op": "hide"})

    def stop(self) -> None:
        """Shut the palette process down. Call once at app exit."""
        with self._lock:
            self._visible = False
            process = self._process
            self._process = None
            self._geometry.clear()
        if process is not None and process.poll() is None:
            try:
                if process.stdin is not None:
                    process.stdin.write(json.dumps({"op": "quit"}) + "\n")
                    process.stdin.flush()
                process.wait(timeout=2)
            except (BrokenPipeError, OSError, ValueError, subprocess.TimeoutExpired):
                process.terminate()

    def apply_settings(self, settings: DwellSettings) -> None:
        self._send(
            {
                "op": "config",
                "opacity": float(settings.palette_opacity),
                "orientation": settings.palette_orientation.value,
            },
            replay_key="config",
        )

    def set_armed(self, action: DwellAction) -> None:
        self._send({"op": "armed", "action": action.value}, replay_key="armed")

    def set_drag_active(self, active: bool) -> None:
        self._send({"op": "drag", "active": bool(active)}, replay_key="drag")

    def set_paused(self, paused: bool) -> None:
        self._send({"op": "paused", "paused": bool(paused)}, replay_key="paused")

    def set_progress(self, action: DwellAction | None, fraction: float) -> None:
        self._send(
            {
                "op": "progress",
                "action": action.value if action is not None else None,
                "fraction": float(fraction),
            }
        )

    def follow(self, x: int, y: int) -> None:
        self._send({"op": "follow", "x": int(x), "y": int(y)})

    def contains(self, x: int, y: int) -> bool:
        return self._geometry.contains(x, y)

    def hovered_action(self, x: int, y: int) -> DwellAction | None:
        return self._geometry.hovered_action(x, y)

    def poll_activations(self) -> list[DwellAction]:
        drained: list[DwellAction] = []
        while True:
            try:
                drained.append(self._activations.get_nowait())
            except queue.Empty:
                return drained

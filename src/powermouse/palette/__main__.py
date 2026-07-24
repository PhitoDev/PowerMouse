"""Tk overlay window for dwell clicking.

Protocol (one JSON object per line):

Parent -> palette (stdin)::

    {"op": "config", "opacity": 0.85, "orientation": "vertical"}
    {"op": "armed", "action": "left"}
    {"op": "drag", "active": true}
    {"op": "paused", "paused": false}
    {"op": "progress", "action": "right" | null, "fraction": 0.4}
    {"op": "follow", "x": 640, "y": 400}
    {"op": "show"} / {"op": "hide"} / {"op": "quit"}

Palette -> parent (stdout)::

    {"event": "layout", "bounds": [x, y, w, h], "buttons": {"left": [x, y, w, h], ...}}
    {"event": "activate", "action": "right"}

The window is borderless, always on top, translucent, and draggable by the
grip row at the top. The grip is also reported as the ``move`` region so the
parent can drive dwell-based repositioning via ``follow`` (the window centers
its grip under the given screen point). It never takes keyboard focus. All
dwell timing and click policy live in the main app; this process is purely
presentational.
Real (OS-level) clicks on its buttons are forwarded as ``activate`` events so
gesture/voice users can also drive the palette directly.
"""
from __future__ import annotations

import json
import queue
import sys
import threading
import tkinter as tk

# Lakers palette (mirrors powermouse.theme; duplicated here so the palette
# process never imports Dear PyGui).
PURPLE = "#552583"
PURPLE_DEEP = "#3d1b5e"
GOLD = "#FDB927"
OFF_WHITE = "#FAF7F2"
GREEN = "#7FCE8A"

BUTTONS = (
    ("left", "Left"),
    ("double", "Double"),
    ("right", "Right"),
    ("middle", "Middle"),
    ("drag_toggle", "Drag"),
    ("pause", "Pause"),
)

DEFAULT_POSITION = (60, 60)
POLL_INTERVAL_MS = 30


class PaletteApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.commands: queue.SimpleQueue[dict] = queue.SimpleQueue()
        self.armed = "left"
        self.drag_active = False
        self.paused = False
        self.orientation = "vertical"
        self._drag_offset: tuple[int, int] | None = None
        self._follow_emit_after: str | None = None
        self._write_lock = threading.Lock()

        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.attributes("-alpha", 0.85)
        except tk.TclError:
            pass  # Some window managers do not support translucency.
        root.configure(bg=PURPLE, highlightthickness=2, highlightbackground=GOLD)
        root.geometry(f"+{DEFAULT_POSITION[0]}+{DEFAULT_POSITION[1]}")

        self.handle = tk.Frame(root, bg=PURPLE_DEEP, cursor="fleur")
        self.grip = tk.Label(
            self.handle, text="⣿⣿", bg=PURPLE_DEEP, fg=GOLD, font=("TkDefaultFont", 8)
        )
        self.flip_button = tk.Label(
            self.handle, text="⇄", bg=PURPLE_DEEP, fg=OFF_WHITE, padx=6
        )
        self.flip_button.bind("<Button-1>", lambda _e: self._emit_activate("flip_layout"))

        self.buttons: dict[str, tk.Label] = {}
        for action, label in BUTTONS:
            button = tk.Label(
                root,
                text=label,
                bg=PURPLE,
                fg=OFF_WHITE,
                padx=14,
                pady=6,
                highlightthickness=1,
                highlightbackground=GOLD,
            )
            button.bind(
                "<Button-1>", lambda _e, a=action: self._emit_activate(a)
            )
            self.buttons[action] = button

        self.progress = tk.Canvas(
            root, height=4, bg=PURPLE_DEEP, highlightthickness=0
        )
        self._progress_fill = self.progress.create_rectangle(
            0, 0, 0, 4, fill=GOLD, width=0
        )

        for widget in (self.handle, self.grip):
            widget.bind("<Button-1>", self._start_move)
            widget.bind("<B1-Motion>", self._on_move)
            widget.bind("<ButtonRelease-1>", lambda _e: self._emit_layout())

        self._layout()
        self._restyle()
        self._start_reader()
        root.after(POLL_INTERVAL_MS, self._poll_commands)

    # -- layout ----------------------------------------------------------

    def _layout(self) -> None:
        for widget in (self.handle, self.progress, *self.buttons.values()):
            widget.pack_forget()
            widget.grid_forget()
        self.grip.pack_forget()
        self.flip_button.pack_forget()

        vertical = self.orientation == "vertical"
        if vertical:
            self.handle.pack(fill="x")
            self.grip.pack(side="left", padx=4)
            self.flip_button.pack(side="right")
            for button in self.buttons.values():
                button.pack(fill="x", padx=6, pady=3)
            self.progress.pack(fill="x", padx=6, pady=(2, 6))
        else:
            self.handle.pack(side="left", fill="y")
            self.grip.pack(side="top", pady=4)
            self.flip_button.pack(side="bottom")
            for button in self.buttons.values():
                button.pack(side="left", padx=3, pady=6)
            self.progress.pack(side="left", fill="y", padx=(2, 6))
            self.progress.configure(height=0, width=4)
        self.root.update_idletasks()

    # -- styling ---------------------------------------------------------

    def _restyle(self) -> None:
        for action, button in self.buttons.items():
            if action == self.armed:
                button.configure(bg=GOLD, fg=PURPLE_DEEP)
            elif action == "drag_toggle" and self.drag_active:
                button.configure(bg=PURPLE, fg=GREEN, highlightbackground=GREEN)
            elif action == "pause" and self.paused:
                button.configure(bg=PURPLE, fg=GREEN, highlightbackground=GREEN)
            else:
                button.configure(bg=PURPLE, fg=OFF_WHITE, highlightbackground=GOLD)
        self.buttons["pause"].configure(text="Resume" if self.paused else "Pause")

    def _set_progress(self, action: str | None, fraction: float) -> None:
        width = self.progress.winfo_width()
        height = self.progress.winfo_height()
        if self.orientation == "vertical":
            self.progress.coords(self._progress_fill, 0, 0, width * fraction, height)
        else:
            self.progress.coords(self._progress_fill, 0, 0, width, height * fraction)
        for name, button in self.buttons.items():
            hovered = fraction > 0 and name == action
            button.configure(
                highlightthickness=2 if hovered else 1,
            )

    # -- window dragging ---------------------------------------------------

    def _start_move(self, event: tk.Event) -> None:
        self._drag_offset = (event.x_root - self.root.winfo_x(),
                             event.y_root - self.root.winfo_y())

    def _on_move(self, event: tk.Event) -> None:
        if self._drag_offset is None:
            return
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _follow(self, x: int, y: int) -> None:
        """Center the grip under (x, y); used for dwell-driven repositioning.

        Layout is re-emitted only after the stream of follow commands goes
        quiet, so per-frame moves don't flood the parent with geometry.
        """
        grip_dx = (
            self.handle.winfo_rootx()
            - self.root.winfo_rootx()
            + self.handle.winfo_width() // 2
        )
        grip_dy = (
            self.handle.winfo_rooty()
            - self.root.winfo_rooty()
            + self.handle.winfo_height() // 2
        )
        self.root.geometry(f"+{x - grip_dx}+{y - grip_dy}")
        self.grip.configure(fg=GREEN)
        if self._follow_emit_after is not None:
            self.root.after_cancel(self._follow_emit_after)
        self._follow_emit_after = self.root.after(150, self._emit_layout_after_follow)

    def _emit_layout_after_follow(self) -> None:
        self._follow_emit_after = None
        self.grip.configure(fg=GOLD)
        self._emit_layout()

    # -- IPC ---------------------------------------------------------------

    def _start_reader(self) -> None:
        def read_stdin():
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    self.commands.put(json.loads(line))
                except json.JSONDecodeError:
                    continue
            self.commands.put({"op": "quit"})

        threading.Thread(target=read_stdin, name="stdin-reader", daemon=True).start()

    def _poll_commands(self) -> None:
        while True:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                break
            self._apply(command)
        self.root.after(POLL_INTERVAL_MS, self._poll_commands)

    def _apply(self, command: dict) -> None:
        match command.get("op"):
            case "config":
                opacity = command.get("opacity")
                if opacity is not None:
                    try:
                        self.root.attributes("-alpha", max(0.3, min(1.0, float(opacity))))
                    except tk.TclError:
                        pass
                orientation = command.get("orientation")
                if orientation in ("vertical", "horizontal") and orientation != self.orientation:
                    self.orientation = orientation
                    self._layout()
                self._emit_layout()
            case "armed":
                self.armed = command.get("action", "left")
                self._restyle()
            case "drag":
                self.drag_active = bool(command.get("active"))
                self._restyle()
            case "paused":
                self.paused = bool(command.get("paused"))
                self._restyle()
            case "progress":
                self._set_progress(
                    command.get("action"), float(command.get("fraction", 0.0))
                )
            case "follow":
                self._follow(int(command.get("x", 0)), int(command.get("y", 0)))
            case "show":
                self.root.deiconify()
                self.root.attributes("-topmost", True)
                self.root.update_idletasks()
                self._emit_layout()
            case "hide":
                self.root.withdraw()
            case "quit":
                self.root.destroy()

    def _send(self, message: dict) -> None:
        with self._write_lock:
            try:
                sys.stdout.write(json.dumps(message) + "\n")
                sys.stdout.flush()
            except (BrokenPipeError, ValueError):
                self.root.destroy()

    def _emit_activate(self, action: str) -> None:
        self._send({"event": "activate", "action": action})

    def _emit_layout(self) -> None:
        self.root.update_idletasks()
        if self.root.state() == "withdrawn":
            return
        bounds = [
            self.root.winfo_rootx(),
            self.root.winfo_rooty(),
            self.root.winfo_width(),
            self.root.winfo_height(),
        ]
        buttons = {}
        for action, button in self.buttons.items():
            buttons[action] = [
                button.winfo_rootx(),
                button.winfo_rooty(),
                button.winfo_width(),
                button.winfo_height(),
            ]
        buttons["flip_layout"] = [
            self.flip_button.winfo_rootx(),
            self.flip_button.winfo_rooty(),
            self.flip_button.winfo_width(),
            self.flip_button.winfo_height(),
        ]
        # The grip doubles as the dwell "move" target. Emitted after
        # flip_layout: the flip button sits inside the handle, and hit-testing
        # honors emission order, so flip keeps priority over its own rect.
        buttons["move"] = [
            self.handle.winfo_rootx(),
            self.handle.winfo_rooty(),
            self.handle.winfo_width(),
            self.handle.winfo_height(),
        ]
        self._send({"event": "layout", "bounds": bounds, "buttons": buttons})


def main() -> None:
    root = tk.Tk()
    PaletteApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

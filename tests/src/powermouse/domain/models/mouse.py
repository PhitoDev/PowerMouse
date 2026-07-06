from enum import Enum


class MouseButton(Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"

    def __str__(self):
        return self.value


class MouseEventType(Enum):
    BUTTON_DOWN = "button_down"
    BUTTON_UP = "button_up"
    MOVE = "move"


class MouseEvent:
    def __init__(self, button: MouseButton, x: int, y: int, event_type: MouseEventType):
        self.button = button
        self.x = x
        self.y = y
        self.event_type = event_type

    def __str__(self):
        return f"{self.button} ({self.x}, {self.y})"


class MouseEventListener:
    def __init__(self, callback):
        self.callback = callback

    def on_event(self, event: MouseEvent):
        self.callback(event)


class ClickInterface(Enum):
    GESTURE = "gesture"
    DWELL = "dwell"
    VOICE = "voice"

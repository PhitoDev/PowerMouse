from enum import Enum


class GestureEvent(Enum):
    LEFT_BLINK = "left_blink"
    RIGHT_BLINK = "right_blink"
    LEFT_SQUINT = "left_squint"
    RIGHT_SQUINT = "right_squint"
    RAISED_EYEBROWS = "raised_eyebrows"
    OPEN_MOUTH = "open_mouth"


class GestureEventListener:
    def __init__(self, callback):
        self.callback = callback

    def on_event(self, event: GestureEvent):
        self.callback(event)

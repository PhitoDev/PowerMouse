from powermouse.domain.controllers.mouse import MouseController
from powermouse.domain.controllers.voice import SpeechRecognizer
from powermouse.domain.models.mouse import ClickInterface, MouseButton, MouseEvent
from powermouse.domain.usecases.mouse_actions import MouseActionCoordinator

CLICK_PHRASES = {
    "click": (MouseButton.LEFT, 1),
    "left click": (MouseButton.LEFT, 1),
    "right click": (MouseButton.RIGHT, 1),
    "middle click": (MouseButton.MIDDLE, 1),
    "double click": (MouseButton.LEFT, 2),
}
HOLD_PHRASES = {
    "hold click": MouseButton.LEFT,
    "hold left click": MouseButton.LEFT,
    "start drag": MouseButton.LEFT,
    "start left drag": MouseButton.LEFT,
    "hold right click": MouseButton.RIGHT,
    "start right drag": MouseButton.RIGHT,
    "hold middle click": MouseButton.MIDDLE,
    "start middle drag": MouseButton.MIDDLE,
}
RELEASE_PHRASES = {
    "release click": MouseButton.LEFT,
    "release left click": MouseButton.LEFT,
    "stop drag": MouseButton.LEFT,
    "stop left drag": MouseButton.LEFT,
    "release right click": MouseButton.RIGHT,
    "stop right drag": MouseButton.RIGHT,
    "release middle click": MouseButton.MIDDLE,
    "stop middle drag": MouseButton.MIDDLE,
}
VOICE_PHRASES = tuple((*CLICK_PHRASES, *HOLD_PHRASES, *RELEASE_PHRASES))


class VoiceToMouseTranslator:
    def __init__(self, coordinator: MouseActionCoordinator | None = None):
        self.coordinator = coordinator or MouseActionCoordinator()

    def translate(self, phrase: str, cursor: tuple[int, int]) -> list[MouseEvent]:
        phrase = phrase.strip().lower()
        if phrase in CLICK_PHRASES:
            button, count = CLICK_PHRASES[phrase]
            return self.coordinator.click(button, cursor, count)
        if phrase in HOLD_PHRASES:
            return self.coordinator.acquire(ClickInterface.VOICE, HOLD_PHRASES[phrase], cursor)
        if phrase in RELEASE_PHRASES:
            return self.coordinator.release(ClickInterface.VOICE, RELEASE_PHRASES[phrase], cursor)
        return []

    def reset_holds(self, cursor: tuple[int, int]) -> list[MouseEvent]:
        return self.coordinator.release_all(ClickInterface.VOICE, cursor)


def voice_clicking_step(
    recognizer: SpeechRecognizer,
    translator: VoiceToMouseTranslator,
    mouse_controller: MouseController,
    cursor: tuple[int, int],
    enabled: bool,
) -> None:
    while (phrase := recognizer.detect_phrase()) is not None:
        if enabled:
            for event in translator.translate(phrase, cursor):
                mouse_controller.handle_event(event)

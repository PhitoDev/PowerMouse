from __future__ import annotations

from powermouse.domain.models.mouse import (
    ClickInterface,
    MouseButton,
    MouseEvent,
    MouseEventType,
)


class MouseActionCoordinator:
    """Coordinates button holds owned by independent click interfaces."""

    def __init__(self) -> None:
        self._owners: dict[MouseButton, set[ClickInterface]] = {}

    @staticmethod
    def _event(
        button: MouseButton,
        kind: MouseEventType,
        cursor: tuple[int, int],
    ) -> MouseEvent:
        return MouseEvent(button, cursor[0], cursor[1], kind)

    def click(
        self,
        button: MouseButton,
        cursor: tuple[int, int],
        count: int = 1,
    ) -> list[MouseEvent]:
        if self._owners.get(button):
            return []
        pair = [
            self._event(button, MouseEventType.BUTTON_DOWN, cursor),
            self._event(button, MouseEventType.BUTTON_UP, cursor),
        ]
        return pair * count

    def acquire(
        self,
        owner: ClickInterface,
        button: MouseButton,
        cursor: tuple[int, int],
    ) -> list[MouseEvent]:
        owners = self._owners.setdefault(button, set())
        if owner in owners:
            return []
        first = not owners
        owners.add(owner)
        return [self._event(button, MouseEventType.BUTTON_DOWN, cursor)] if first else []

    def release(
        self,
        owner: ClickInterface,
        button: MouseButton,
        cursor: tuple[int, int],
    ) -> list[MouseEvent]:
        owners = self._owners.get(button)
        if not owners or owner not in owners:
            return []
        owners.remove(owner)
        if owners:
            return []
        del self._owners[button]
        return [self._event(button, MouseEventType.BUTTON_UP, cursor)]

    def is_owned(self, owner: ClickInterface, button: MouseButton) -> bool:
        return owner in self._owners.get(button, set())

    def release_all(self, owner: ClickInterface, cursor: tuple[int, int]) -> list[MouseEvent]:
        events = []
        for button in list(self._owners):
            events.extend(self.release(owner, button, cursor))
        return events

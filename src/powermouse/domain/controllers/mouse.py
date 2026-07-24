from powermouse.domain.models.mouse import MouseEvent


class MouseController:
    def handle_event(self, mouse: MouseEvent):
        raise NotImplementedError

    def get_position(self) -> tuple[int, int]:
        """Current OS cursor position. Used as the cursor source for the
        clicking interfaces when face tracking is disabled."""
        raise NotImplementedError

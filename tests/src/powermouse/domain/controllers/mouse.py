from powermouse.domain.models.mouse import MouseEvent


class MouseController:
    def handle_event(self, mouse: MouseEvent):
        raise NotImplementedError

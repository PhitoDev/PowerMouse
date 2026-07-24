from __future__ import annotations

from powermouse.domain.models.dwell import DwellAction, DwellSettings


class DwellPaletteController:
    """Port for the floating dwell-action palette.

    The palette is purely presentational: all dwell timing and click policy
    live in ``powermouse.domain.usecases.dwell_clicking``. Implementations
    report their on-screen geometry (``contains`` / ``hovered_action``) and
    surface direct button activations (real clicks on the palette window)
    through ``poll_activations``.
    """

    def show(self) -> None:
        raise NotImplementedError

    def hide(self) -> None:
        raise NotImplementedError

    def apply_settings(self, settings: DwellSettings) -> None:
        raise NotImplementedError

    def set_armed(self, action: DwellAction) -> None:
        raise NotImplementedError

    def set_drag_active(self, active: bool) -> None:
        raise NotImplementedError

    def set_paused(self, paused: bool) -> None:
        raise NotImplementedError

    def set_progress(self, action: DwellAction | None, fraction: float) -> None:
        """Report dwell progress (0..1). ``action`` is the hovered palette
        button, or ``None`` for an on-screen dwell."""
        raise NotImplementedError

    def follow(self, x: int, y: int) -> None:
        """Reposition the palette so its grab handle sits under ``(x, y)``.

        Called once per frame while the user has picked the palette up by
        dwelling on its grip (``DwellAction.MOVE``)."""
        raise NotImplementedError

    def contains(self, x: int, y: int) -> bool:
        raise NotImplementedError

    def hovered_action(self, x: int, y: int) -> DwellAction | None:
        raise NotImplementedError

    def poll_activations(self) -> list[DwellAction]:
        raise NotImplementedError

"""Entry point for python -m powermouse (briefcase) and direct script use."""
import os


def main() -> None:
    if os.environ.get("POWERMOUSE_PALETTE") == "1":
        # We are the dwell-palette child process. In a Briefcase-packaged app
        # the stub binary always reruns this module regardless of argv, so the
        # spawner (adapters/dwell_palette.py) sets this env var to route the
        # child here instead of opening another main window. Imported lazily
        # so the palette process skips the heavy main-app imports.
        from powermouse.palette.__main__ import main as palette_main

        palette_main()
        return

    from powermouse.main import main as app_main

    app_main()


if __name__ == "__main__":
    main()

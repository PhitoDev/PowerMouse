"""Floating dwell-action palette.

Runs as a separate process (``python -m powermouse.palette``) because Tk
requires the process main thread on macOS, which Dear PyGui's render loop
already owns in the main app. The app talks to it over JSON lines on
stdin/stdout; see ``powermouse.adapters.dwell_palette``.
"""

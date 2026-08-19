# Changelog

## v0.3.3

- Fixed voice clicking silently doing nothing in the packaged macOS app: the
  signed, hardened-runtime app was missing the
  `com.apple.security.device.audio-input` entitlement, so macOS never showed
  the microphone permission prompt and delivered silent audio. The app now
  requests microphone access on first use of voice clicking.

## v0.3.2

- Fixed the packaged macOS app crashing at startup: packaged builds installed
  unpinned latest dependencies (mediapipe 1.0, OpenCV 5.0) instead of the
  locked versions used when running from source, crashing the native
  tracking and voice layers. Packaged builds now install the exact locked
  dependency versions on macOS and Windows.
- The dwell palette now works in packaged builds: Tcl/Tk is bundled into the
  macOS and Windows apps (the stock Briefcase Python ships without tkinter),
  and the Linux packages declare the tkinter system dependency (python3-tk
  on Debian, tk on Arch).
- The dwell palette subprocess stops respawning after several immediate
  exits instead of looping forever.

## v0.3.1

- Fixed the packaged macOS app endlessly opening new main windows instead of
  the dwell palette: the app launcher stub always reruns the main entry
  point, so the palette subprocess is now routed through an environment
  variable dispatch instead of `python -m`.

## v0.3.0

- Implemented dwell clicking with a translucent floating palette offering
  left, double, right, and middle clicks, drag, pause, and layout flip.
- The palette can be repositioned hands-free: dwell on its grip to pick it
  up, let it follow the cursor, then dwell again to drop it.
- Face tracking is now optional and persisted per profile, so PowerMouse can
  be used for clicking alone alongside any pointing device.
- Dwell and voice clicking keep working when the camera is unavailable.
- Dwell settings (dwell time, radius, palette opacity, and orientation) are
  persisted per profile.
- Tracking parameter controls are greyed out while face tracking is off.

## v0.2.0

- Implemented voice clicking.
- Several UI and UX improvements.
- Fixed the FPS count for the camera widget.

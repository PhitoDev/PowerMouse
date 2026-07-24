<div align="center">

<h1>PowerMouse</h1>

<p><strong>A versatile hands-free mouse.</strong><br>
Move the cursor with your head. Click with gestures, dwell, or your voice — or any combination of the three.</p>

<p>
  <a href="https://github.com/PhitoDev/PowerMouse/releases"><img alt="Download the latest release" src="https://img.shields.io/github/v/release/PhitoDev/PowerMouse?label=download&color=blue"></a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-blue">
  <img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-green">
</p>

<h3><a href="https://github.com/PhitoDev/PowerMouse/releases">⬇ Download the latest version</a></h3>

</div>

PowerMouse uses face detection technology to let you control the mouse cursor on your computer without your hands. It is built for people with physical disabilities that make using a standard mouse difficult — but every input method is optional and composable, so you can shape it to your needs:

- Use face tracking to move the cursor **and** click hands-free.
- Or turn face tracking off and use PowerMouse **for clicking alone**, alongside any pointing device you already use.

## Key Features

| **Feature** | **Description** | **Status** |
|---------|-------------|-----------|
| Cursor Movement | Move the mouse cursor on the screen with head movement. Optional and per-profile — turn it off to use PowerMouse for clicking alone. | Implemented |
| Gesture Clicking | Perform different mouse clicks with a variety of facial gestures. | Implemented |
| Dwell Clicking | Perform clicks by letting the cursor *dwell* on a position for a short moment, with a floating on-screen palette to pick the click type. | Implemented |
| Voice Clicking | Use voice commands to perform different mouse clicks, holds, and releases. | Implemented |
| Profiles | Save tracking, clicking, camera, and microphone settings per person or per situation, persisted between sessions. | Implemented |
| Camera Recovery | If the camera disconnects, clicking keeps working while a recovery panel helps you pick a new camera. | Implemented |

## The UI at a Glance

<table>
<tr>
<td width="55%" valign="top">

<h3>🪟 Main Window</h3>

<ul>
  <li><strong>Profiles panel</strong> — create, activate, and delete per-user profiles.</li>
  <li><strong>Camera panel</strong> — pick a camera and watch a live preview of what the tracker sees.</li>
  <li><strong>Tracking tab</strong> — toggle face tracking on/off and tune speed, acceleration, sensitivity, smoothness, deadzone, and active area. Controls grey out while tracking is off.</li>
  <li><strong>Clicking tab</strong> — enable any mix of gesture, voice, and dwell clicking, choose a microphone, and tune dwell time, radius, palette opacity, and orientation.</li>
  <li><strong>Save / Revert</strong> — settings changes apply live and persist only when you save.</li>
</ul>

</td>
<td width="45%" valign="top">

<h3>🎛️ Floating Dwell Palette</h3>

<p>A small translucent palette that stays on top of every window. Rest the cursor on a button to arm it, then dwell anywhere on screen to fire it.</p>

<table align="center">
  <tr><td align="center">⠿ <em>grip — dwell to pick up &amp; move</em></td></tr>
  <tr><td align="center">🖱️ Left Click</td></tr>
  <tr><td align="center">🖱️🖱️ Double Click</td></tr>
  <tr><td align="center">🖱️ Right Click</td></tr>
  <tr><td align="center">🖱️ Middle Click</td></tr>
  <tr><td align="center">✊ Drag (toggle)</td></tr>
  <tr><td align="center">⏸ Pause Dwell</td></tr>
  <tr><td align="center">↔ Flip Layout</td></tr>
</table>

<p align="center"><sub>Everything on the palette is operated by dwelling — no clicks required, ever.</sub></p>

</td>
</tr>
</table>

## Clicking Without Tracking

Face tracking is on by default, but it is a per-profile setting like everything else. Turn it off in the <strong>Tracking</strong> tab and:

- The cursor is yours — move it with a trackpad, joystick, eye tracker, or any other device.
- Dwell, voice, and gesture clicking all act at the **real cursor position**.
- Dwell and voice clicking keep working even if no camera is available.

## Apple Voice Control

PowerMouse uses DearPyGui for its interface. DearPyGui renders controls through
a GPU surface, so macOS Voice Control may not show numbered labels for buttons,
sliders, and tabs the way it does for native AppKit controls.

For better Voice Control support on macOS, PowerMouse provides keyboard
shortcuts for common actions. You can say the built-in Voice Control phrase
directly, or create custom Voice Control commands that press these shortcuts.

| PowerMouse action | Keyboard shortcut | Voice Control phrase |
| --- | --- | --- |
| New profile | <kbd>Command</kbd>-<kbd>N</kbd> | “Press Command N” |
| Save settings | <kbd>Command</kbd>-<kbd>S</kbd> | “Press Command S” |
| Revert settings | <kbd>Command</kbd>-<kbd>R</kbd> | “Press Command R” |
| Refresh cameras | <kbd>Command</kbd>-<kbd>Shift</kbd>-<kbd>R</kbd> | “Press Command Shift R” |
| Set selected profile active | <kbd>Command</kbd>-<kbd>Return</kbd> | “Press Command Return” |
| Delete selected profile | <kbd>Command</kbd>-<kbd>Delete</kbd> | “Press Command Delete” |
| Show Tracking settings | <kbd>Command</kbd>-<kbd>1</kbd> | “Press Command 1” |
| Show Clicking settings | <kbd>Command</kbd>-<kbd>2</kbd> | “Press Command 2” |

<details>
<summary><strong>Suggested custom Voice Control commands</strong></summary>

| Say this | Perform this shortcut |
| --- | --- |
| “New PowerMouse profile” | <kbd>Command</kbd>-<kbd>N</kbd> |
| “Save PowerMouse settings” | <kbd>Command</kbd>-<kbd>S</kbd> |
| “Revert PowerMouse settings” | <kbd>Command</kbd>-<kbd>R</kbd> |
| “Refresh PowerMouse cameras” | <kbd>Command</kbd>-<kbd>Shift</kbd>-<kbd>R</kbd> |
| “Use selected PowerMouse profile” | <kbd>Command</kbd>-<kbd>Return</kbd> |
| “Delete PowerMouse profile” | <kbd>Command</kbd>-<kbd>Delete</kbd> |
| “PowerMouse tracking settings” | <kbd>Command</kbd>-<kbd>1</kbd> |
| “PowerMouse clicking settings” | <kbd>Command</kbd>-<kbd>2</kbd> |

</details>

# PowerMouse
### [Download the latest version!](https://github.com/PhitoDev/PowerMouse/releases)

PowerMouse is a versatile hands-free mouse that uses face detection technology to enable a user to control the mouse cursor on their computer. The user will have the option to execute different mouse clicking functions using face gestures, dwell clicking, voice clicking, or any combination of the three.
### **Target Audience**
The target audience is people with physical disabilities that make using a standard mouse difficult.

### **Key Features** 
| **Feature** | **Description** | **Status** |
|---------|-------------|-----------|
| Cursor Movement | The user will be able to move the mouse cursor on the screen with head movement. | Implemented |
| Gesture Clicking | The user will be able perform different mouse clicks with a variety of facial gestures. | Implemented |
| Dwell Clicking | The user will be able to perform different mouse clicks by letting the mouse cursor *dwell* on a position for a short moment. | Coming Soon |
| Voice Clicking | The user will be able to use voice commands to perform different mouse clicks. | Coming Soon |

## Apple Voice Control

PowerMouse uses DearPyGui for its interface. DearPyGui renders controls through
a GPU surface, so macOS Voice Control may not show numbered labels for buttons,
sliders, and tabs the way it does for native AppKit controls.

For better Voice Control support on macOS, PowerMouse provides keyboard
shortcuts for common actions. You can say the built-in Voice Control phrase
directly, or create custom Voice Control commands that press these shortcuts.

| PowerMouse action | Keyboard shortcut | Voice Control phrase |
| --- | --- | --- |
| New profile | `Command-N` | “Press Command N” |
| Save settings | `Command-S` | “Press Command S” |
| Revert settings | `Command-R` | “Press Command R” |
| Refresh cameras | `Command-Shift-R` | “Press Command Shift R” |
| Set selected profile active | `Command-Return` | “Press Command Return” |
| Delete selected profile | `Command-Delete` | “Press Command Delete” |
| Show Tracking settings | `Command-1` | “Press Command 1” |
| Show Clicking settings | `Command-2` | “Press Command 2” |

Suggested custom Voice Control commands:

| Say this | Perform this shortcut |
| --- | --- |
| “New PowerMouse profile” | `Command-N` |
| “Save PowerMouse settings” | `Command-S` |
| “Revert PowerMouse settings” | `Command-R` |
| “Refresh PowerMouse cameras” | `Command-Shift-R` |
| “Use selected PowerMouse profile” | `Command-Return` |
| “Delete PowerMouse profile” | `Command-Delete` |
| “PowerMouse tracking settings” | `Command-1` |
| “PowerMouse clicking settings” | `Command-2` |

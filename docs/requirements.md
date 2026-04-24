# **Requirements Document: PowerMouse**
---
## 1. **Product Overview**
### **Description** 
PowerMouse is a versatile hands-free mouse that uses face detection technology to enable a user to control the mouse cursor on their computer. The user will have the option to execute different mouse clicking functions using face gestures, dwell clicking, voice clicking, or any combination of the three.
### **Target Audience**
The target audience is people with physical disabilities that make using a standard mouse difficult.

### **Key Features** 
| **Feature** | **Description** |
|---------|-------------|
| Cursor Movement | The user will be able to move the mouse cursor on the screen with head movement. |
| Gesture Clicking | The user will be able perform different mouse clicks with a variety of facial gestures. |
| Dwell Clicking | The user will be able to perform different mouse clicks by letting the mouse cursor *dwell* on a position for a short moment. |
| Voice Clicking | The user will be able to use voice commands to perform different mouse clicks.

## 2. **Functional Requirements**
---
### **Use Cases** 
 1. **Profile Management**
  * As a user, I want to create profiles to manage my PowerMouse settings.
  * As a user, I want my profile to remember which camera to user, for PowerMouse 
  * As a user, I want my profile to remember my acceleration, speed and sensitivity settings for face tracking.
  * As a user, I want my profile to remember my mouse clicking configuration.
2. **Onboarding**
  * As a user, the first time I open the app, I want it to prompt me to create a profile.
  * As a user, I want to select which camera to use from my available devices.
  * As a user, I want to do initial calibration of the camera for tracking.
  * As a user, I want to configure which clicking options I want to use.
 3. **Face Tracking**
  * As a user, I want to move the mouse cursor with my head movements.
  * As a user, I want to adjust the the acceleration, speed and sensitivity of the mouse cursor.
 4. **Gesture Clicking**
  * As a user, I want to perform a left click when I wink my left eye.
  * As a user I want to perform a right click when I wink my right eye.
  * As a user, I want to toggle holding left click down with opening my jaw.
  * As a user, I want to toggle holding down right click with squinting my right eye.
  * As a user I want to perform a middle click when I raise both eyebrows.
  * As a user, I want to perform a double click when I squint my left eye.
 5. **Dwell Clicking**
  * As a user, I want a small, transparent, docked window with different click modes to choose from.
  * As a user, I want to dwell over a button on the docked window to select a click mode.
  * As a user, I want the following click modes as options:
  
    * **Pause Clicking**
    * **Left Click**
    * **Right Click**
    * **Middle Click**
    * **Drag Click**
  * As a user, I want drag click to work with left, right and middle click, dependent on which is active.
 6. **Voice Clicking**(TODO)

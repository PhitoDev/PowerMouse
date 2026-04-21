# **PowerMouse: Architectural Design Document**

**Document Version:** 1.0  
**Project:** PowerMouse Accessibility Controller  
**Primary Language:** Python

## **1\. System Overview**

PowerMouse is an accessibility-first desktop application designed to provide users with hands-free mouse control using low-latency face tracking. Prioritizing smoothness, responsiveness, and minimal visual fatigue, the architecture bypasses traditional, bloated abstraction layers in favor of direct OS system calls, native neural network pipelines, and rigorous signal processing.

## **2\. Technology Stack**

| Component | Technology Chosen | Architectural Rationale   |
| :---- | :---- | :---- |
| **Core Language** | Python | Unmatched ecosystem for computer vision. Allows rapid iteration of coordinate math and smoothing algorithms over systems languages like Rust. |
| **Video Capture** | OpenCV | Provides solid and well established API with seamless integration with MediaPipe |
| **Computer Vision** | Google MediaPipe (\`FaceLandmarker\`) | Provides native, C++ optimized Deep Learning models. Offers 478 3D facial landmarks and 52 facial blendshapes simultaneously in O(1) inference time. |
| **OS Input API** | \`mouse\` library / OS \`ctypes\` | Bypasses high-level GUI wrappers (like PyAutoGUI) to communicate directly with OS kernels (\`user32.dll\`, \`Quartz\`), minimizing input latency. |
| **GUI Framework** | DearPyGui | Hardware-accelerated rendering ensures the user interface does not steal CPU cycles from the critical tracking thread. |
| Data Persistence | SQLAlchemy | Well established and easy to use framework for simple profile management. | 

## **3\. Multi-Threaded Execution Pipeline**

To maintain a 60+ FPS tracking loop without input blocking, the system operates on a decoupled asynchronous architecture.

* **Thread 1 (Capture):** Continuously pulls frames from the OpenCV \`VideoCapture\` buffer.  
* **Thread 2 (Inference Callback):** MediaPipe runs in \`LIVE\_STREAM\` mode. As soon as the neural network finishes processing a frame, it triggers an asynchronous Python callback function containing the spatial data.  
* **Thread 3 (Control & Filtering):** Processes the callback data, applies mathematical smoothing (EMA), checks for gesture thresholds, and issues direct OS commands.

## **4\. Tracking and Input Mechanisms**

### **4.1. Cursor Movement (Face Landmarks)**

Cursor movement is determined by tracking the center point of the user's nose. This provides the most stable pivot point for head rotations. Raw 3D coordinates are normalized and mapped to the 2D resolution of the primary display.

### **4.2. Action Triggers (Facial Blendshapes)**

Clicking actions are triggered via MediaPipe's pre-calculated Facial Blendshapes, avoiding the computational overhead of secondary classification models (e.g., OpenCV KNN). Blendshapes provide float values \[0.0, 1.0\] for muscle activation:

* **Left Click:** \`eyeBlinkLeft\`  
* **Left Double Click:** \`eyeSquintLeft\`
* **Right Click:** \`eyeBlinkRight\`  
* **Middle Click:** \`browInnerUp\`
* **Drag/Scroll Mode Toggle:** \`jawOpen\`
* **Drag Right Click Toggle:** \`eyeSquintRight\`

## **5\. Signal Processing & Smoothness Engine**

To ensure the application feels like a locked-in accessibility tool and prevents visual fatigue from sensor noise, raw data must pass through three filtering stages before reaching the OS.

### **5.1. Exponential Moving Average (EMA) Filter**

High-frequency webcam jitter is removed using an EMA filter, which offers near-zero computational cost compared to Kalman filters. The formula applied is: *St \= α · Xt \+ (1 \- α) · St-1*

### **5.2. Non-Linear Acceleration & Deadzones**

A radial deadzone (e.g., 5 pixels) is enforced at the center of the user's gaze to allow for resting states without micro-cursor drifts. Movement beyond the deadzone uses an exponential acceleration curve (Vout \= Vinn) to grant fine pixel control for small head movements and rapid panning for larger head sweeps.

### **5.3. Hysteresis for Click Stability**

To prevent "flicker clicking" caused by intermediate blink states, action triggers utilize dual-threshold hysteresis. The eye must exceed a high activation threshold to trigger the event, and drop below a separate, lower threshold to reset it.

\# Python Implementation of Signal Processing Core

class SmoothnessEngine:  
    def \_\_init\_\_(self, alpha\_move=0.2, alpha\_click=0.5):  
        self.alpha\_move \= alpha\_move  
        self.alpha\_click \= alpha\_click  
        self.smoothed\_x \= 0  
        self.smoothed\_y \= 0  
        self.is\_clicking \= False  
          
    def filter\_movement(self, raw\_x, raw\_y):  
        \# Exponential Moving Average for positional data  
        self.smoothed\_x \= (self.alpha\_move \* raw\_x) \+ ((1 \- self.alpha\_move) \* self.smoothed\_x)  
        self.smoothed\_y \= (self.alpha\_move \* raw\_y) \+ ((1 \- self.alpha\_move) \* self.smoothed\_y)  
        return self.smoothed\_x, self.smoothed\_y

    def check\_click\_hysteresis(self, blink\_score, high\_thresh=0.6, low\_thresh=0.4):  
        \# Dual-thresholding to prevent flicker  
        if blink\_score \> high\_thresh and not self.is\_clicking:  
            self.is\_clicking \= True  
            return "CLICK\_DOWN"  
        elif blink\_score \< low\_thresh and self.is\_clicking:  
            self.is\_clicking \= False  
            return "CLICK\_UP"  
        return "HOLD"

## **6\. Future Considerations**

While the current architecture optimizes for accessibility via software APIs, future iterations targeting video games with kernel-level anti-cheat (e.g., Vanguard) will require migrating the output layer from software injection (\`SendInput\`) to a Hardware HID Proxy (e.g., passing smoothed coordinates via Serial to an ATmega32U4 microcontroller).

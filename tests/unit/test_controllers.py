"""Unit tests for the abstract controllers in ``powermouse.domain.controllers``.

The base classes deliberately raise ``NotImplementedError`` so concrete
adapters must implement them. The fakes in :mod:`tests.conftest` are the
test-side adapters used by the use cases.
"""
from __future__ import annotations

import pytest

from powermouse.domain.controllers.camera import CameraController
from powermouse.domain.controllers.devices import DeviceManager
from powermouse.domain.controllers.inference import InferenceController
from powermouse.domain.controllers.mouse import MouseController
from powermouse.domain.controllers.profile import ProfileManager
from powermouse.domain.controllers.voice import (
    MicrophoneCapture,
    MicrophoneManager,
    SpeechRecognizer,
)
from powermouse.domain.models.mouse import MouseButton, MouseEvent, MouseEventType
from powermouse.domain.models.microphone import Microphone


class TestCameraControllerBase:
    def test_methods_raise(self, camera):
        controller = CameraController(camera)
        with pytest.raises(NotImplementedError):
            controller.update_frame()
        with pytest.raises(NotImplementedError):
            controller.start_stream()
        with pytest.raises(NotImplementedError):
            controller.stop_stream()


class TestInferenceControllerBase:
    def test_process_frame_raises(self):
        controller = InferenceController()
        with pytest.raises(NotImplementedError):
            controller.process_frame(frame_bgr=None, timestamp_ms=0)
        with pytest.raises(NotImplementedError):
            controller.get_cursor_position()
        with pytest.raises(NotImplementedError):
            controller.detect_gesture()


class TestMouseControllerBase:
    def test_handle_event_raises(self):
        with pytest.raises(NotImplementedError):
            MouseController().handle_event(
                MouseEvent(MouseButton.LEFT, 0, 0, MouseEventType.MOVE)
            )


class TestProfileManagerBase:
    def test_methods_raise(self, sample_profile):
        manager = ProfileManager()
        with pytest.raises(NotImplementedError):
            manager.create_profile(sample_profile)
        with pytest.raises(NotImplementedError):
            manager.list_profiles()
        with pytest.raises(NotImplementedError):
            manager.get_active_profile()
        with pytest.raises(NotImplementedError):
            manager.get_profile("1")
        with pytest.raises(NotImplementedError):
            manager.delete_profile(1)
        with pytest.raises(NotImplementedError):
            manager.update_profile(1, sample_profile)


class TestDeviceManagerBase:
    def test_methods_raise(self):
        manager = DeviceManager()
        with pytest.raises(NotImplementedError):
            manager.get_devices()
        with pytest.raises(NotImplementedError):
            manager._get_devices_linux()
        with pytest.raises(NotImplementedError):
            manager._get_devices_windows()


class TestVoiceControllerBases:
    def test_microphone_manager_methods_raise(self):
        manager = MicrophoneManager()
        with pytest.raises(NotImplementedError):
            manager.get_microphones()
        with pytest.raises(NotImplementedError):
            manager.get_default_microphone()

    def test_microphone_capture_methods_raise(self):
        capture = MicrophoneCapture()
        with pytest.raises(NotImplementedError):
            _ = capture.sample_rate
        with pytest.raises(NotImplementedError):
            capture.start(Microphone("1", "Test"))
        with pytest.raises(NotImplementedError):
            capture.read()
        with pytest.raises(NotImplementedError):
            capture.detect_error()
        with pytest.raises(NotImplementedError):
            capture.stop()

    def test_speech_recognizer_methods_raise(self):
        recognizer = SpeechRecognizer()
        with pytest.raises(NotImplementedError):
            recognizer.start(16_000)
        with pytest.raises(NotImplementedError):
            recognizer.process_audio(b"")
        with pytest.raises(NotImplementedError):
            recognizer.detect_phrase()
        with pytest.raises(NotImplementedError):
            recognizer.reset()
        with pytest.raises(NotImplementedError):
            recognizer.stop()

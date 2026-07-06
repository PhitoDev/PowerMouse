"""Unit tests for inference signal-processing helpers."""
from __future__ import annotations

from powermouse.adapters.inference import _SmoothnessEngine
from powermouse.domain.models.camera import FaceTrackerSettings


class TestSmoothnessEngine:
    def test_faster_nose_movement_travels_farther(self, camera):
        slow_settings = FaceTrackerSettings(
            camera=camera,
            speed=1.0,
            acceleration=2.0,
            smoothness=0.0,
            deadzone_radius_px=0,
        )
        fast_settings = FaceTrackerSettings(
            camera=camera,
            speed=1.0,
            acceleration=2.0,
            smoothness=0.0,
            deadzone_radius_px=0,
        )
        slow = _SmoothnessEngine(slow_settings, screen_size=(1000, 1000))
        fast = _SmoothnessEngine(fast_settings, screen_size=(1000, 1000))

        assert slow.update(500.0, 500.0, 0) == (500, 500)
        assert fast.update(500.0, 500.0, 0) == (500, 500)

        slow_cursor = slow.update(510.0, 500.0, 100)
        fast_cursor = fast.update(510.0, 500.0, 10)

        assert fast_cursor[0] > slow_cursor[0]
        assert slow_cursor[1] == fast_cursor[1] == 500

    def test_deadzone_accumulates_slow_intentional_movement(self, camera):
        settings = FaceTrackerSettings(
            camera=camera,
            speed=1.0,
            acceleration=0.0,
            smoothness=0.0,
            deadzone_radius_px=5,
        )
        engine = _SmoothnessEngine(settings, screen_size=(1000, 1000))

        assert engine.update(500.0, 500.0, 0) == (500, 500)
        assert engine.update(503.0, 500.0, 100) == (500, 500)

        assert engine.update(506.0, 500.0, 200) == (506, 500)

    def test_speed_controls_base_relative_distance(self, camera):
        slow_settings = FaceTrackerSettings(
            camera=camera,
            speed=1.0,
            acceleration=0.0,
            smoothness=0.0,
            deadzone_radius_px=0,
        )
        fast_settings = FaceTrackerSettings(
            camera=camera,
            speed=2.0,
            acceleration=0.0,
            smoothness=0.0,
            deadzone_radius_px=0,
        )
        slow = _SmoothnessEngine(slow_settings, screen_size=(1000, 1000))
        fast = _SmoothnessEngine(fast_settings, screen_size=(1000, 1000))

        slow.update(500.0, 500.0, 0)
        fast.update(500.0, 500.0, 0)

        assert slow.update(510.0, 500.0, 100) == (510, 500)
        assert fast.update(510.0, 500.0, 100) == (520, 500)

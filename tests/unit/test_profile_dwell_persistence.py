"""Persistence tests for DwellSettings on the SQLAlchemy profile adapter."""
from __future__ import annotations

from sqlalchemy import create_engine, text

from powermouse.adapters.profile import SqlAlchemyProfileManager
from powermouse.domain.models.dwell import DwellSettings, PaletteOrientation


class TestDwellSettingsRoundTrip:
    def test_defaults_persist(self, profile_manager, sample_profile):
        created = profile_manager.create_profile(sample_profile)
        loaded = profile_manager.get_profile(str(created.profile_id))
        assert loaded.dwell_settings == DwellSettings()

    def test_custom_settings_round_trip(self, profile_manager, sample_profile):
        sample_profile.dwell_settings = DwellSettings(
            dwell_time_ms=1500,
            radius_px=40,
            palette_opacity=0.6,
            palette_orientation=PaletteOrientation.HORIZONTAL,
        )
        created = profile_manager.create_profile(sample_profile)
        loaded = profile_manager.get_profile(str(created.profile_id))
        assert loaded.dwell_settings.dwell_time_ms == 1500
        assert loaded.dwell_settings.radius_px == 40
        assert loaded.dwell_settings.palette_opacity == 0.6
        assert (
            loaded.dwell_settings.palette_orientation
            is PaletteOrientation.HORIZONTAL
        )

    def test_update_persists_dwell_changes(self, profile_manager, sample_profile):
        created = profile_manager.create_profile(sample_profile)
        created.dwell_settings.dwell_time_ms = 700
        created.dwell_settings.palette_orientation = PaletteOrientation.HORIZONTAL
        profile_manager.update_profile(created.profile_id, created)
        loaded = profile_manager.get_profile(str(created.profile_id))
        assert loaded.dwell_settings.dwell_time_ms == 700
        assert (
            loaded.dwell_settings.palette_orientation
            is PaletteOrientation.HORIZONTAL
        )


class TestDwellSchemaMigration:
    def test_legacy_database_gains_dwell_columns_with_defaults(self, tmp_path):
        db_path = tmp_path / "profiles.db"
        db_url = f"sqlite:///{db_path}"

        # Simulate a pre-dwell database: the profiles table without any
        # dwell_* columns, holding one row.
        engine = create_engine(db_url, future=True)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE profiles (
                        profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR NOT NULL,
                        is_active BOOLEAN NOT NULL,
                        speed FLOAT NOT NULL,
                        acceleration FLOAT NOT NULL,
                        sensitivity_x FLOAT NOT NULL,
                        sensitivity_y FLOAT NOT NULL,
                        smoothness FLOAT NOT NULL,
                        deadzone_radius_px INTEGER NOT NULL,
                        active_area_x_min FLOAT NOT NULL,
                        active_area_x_max FLOAT NOT NULL,
                        active_area_y_min FLOAT NOT NULL,
                        active_area_y_max FLOAT NOT NULL,
                        click_threshold_high FLOAT NOT NULL,
                        click_threshold_low FLOAT NOT NULL,
                        camera_id VARCHAR NOT NULL,
                        camera_name VARCHAR NOT NULL,
                        click_interfaces JSON NOT NULL,
                        microphone_id VARCHAR,
                        microphone_name VARCHAR
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO profiles (
                        name, is_active, speed, acceleration,
                        sensitivity_x, sensitivity_y, smoothness,
                        deadzone_radius_px,
                        active_area_x_min, active_area_x_max,
                        active_area_y_min, active_area_y_max,
                        click_threshold_high, click_threshold_low,
                        camera_id, camera_name, click_interfaces
                    ) VALUES (
                        'Legacy', 1, 3.0, 2.5,
                        1.0, 1.0, 0.5,
                        5,
                        0.35, 0.65, 0.35, 0.65,
                        0.6, 0.4,
                        '0', 'Cam', '{}'
                    )
                    """
                )
            )
        engine.dispose()

        manager = SqlAlchemyProfileManager(db_url=db_url)
        loaded = manager.get_profile("1")
        assert loaded.name == "Legacy"
        assert loaded.dwell_settings == DwellSettings()
        # tracking_enabled is added by the same additive upgrade pass.
        assert loaded.tracking_enabled is True


class TestTrackingEnabledRoundTrip:
    def test_defaults_to_enabled(self, profile_manager, sample_profile):
        created = profile_manager.create_profile(sample_profile)
        loaded = profile_manager.get_profile(str(created.profile_id))
        assert loaded.tracking_enabled is True

    def test_disabled_round_trips(self, profile_manager, sample_profile):
        sample_profile.tracking_enabled = False
        created = profile_manager.create_profile(sample_profile)
        loaded = profile_manager.get_profile(str(created.profile_id))
        assert loaded.tracking_enabled is False

    def test_update_persists_toggle(self, profile_manager, sample_profile):
        created = profile_manager.create_profile(sample_profile)
        created.tracking_enabled = False
        profile_manager.update_profile(created.profile_id, created)
        loaded = profile_manager.get_profile(str(created.profile_id))
        assert loaded.tracking_enabled is False

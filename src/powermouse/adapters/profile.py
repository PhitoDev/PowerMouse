from __future__ import annotations

from typing import Iterable, List, Optional

import numpy as np
from platformdirs import user_data_path
from sqlalchemy import JSON, Boolean, Float, Integer, String, create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from powermouse.domain.controllers.profile import ProfileManager
from powermouse.domain.models.camera import (
    DEFAULT_ACTIVE_AREA,
    DEFAULT_TRACKING_ACCELERATION,
    DEFAULT_TRACKING_SPEED,
    LEGACY_DEFAULT_ACTIVE_AREA,
    Camera,
    FaceTrackerSettings,
)
from powermouse.domain.models.dwell import (
    DEFAULT_DWELL_RADIUS_PX,
    DEFAULT_DWELL_TIME_MS,
    DEFAULT_PALETTE_OPACITY,
    DwellSettings,
    PaletteOrientation,
)
from powermouse.domain.models.mouse import ClickInterface
from powermouse.domain.models.microphone import Microphone
from powermouse.domain.models.profile import Profile


_APP_NAME = "PowerMouse"
_APP_AUTHOR = "dev.phito"
_DEFAULT_DB_DIR = user_data_path(_APP_NAME, _APP_AUTHOR)
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "profiles.db"
_PLACEHOLDER_FRAME = np.zeros((0, 0, 3), dtype=np.uint8)
_LEGACY_DEFAULT_TRACKING_SPEEDS = (1.0,)
_LEGACY_DEFAULT_TRACKING_ACCELERATIONS = (1.0, 1.5)
_TRACKING_DEFAULTS_MIGRATION_VERSION = 1
_MICROPHONE_MIGRATION_VERSION = 2


class _Base(DeclarativeBase):
    pass


class ProfileRow(_Base):
    __tablename__ = "profiles"

    profile_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tracking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Flattened FaceTrackerSettings.
    speed: Mapped[float] = mapped_column(
        Float, nullable=False, default=DEFAULT_TRACKING_SPEED
    )
    acceleration: Mapped[float] = mapped_column(
        Float, nullable=False, default=DEFAULT_TRACKING_ACCELERATION
    )
    sensitivity_x: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    sensitivity_y: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    smoothness: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    deadzone_radius_px: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    active_area_x_min: Mapped[float] = mapped_column(
        Float, nullable=False, default=DEFAULT_ACTIVE_AREA[0]
    )
    active_area_x_max: Mapped[float] = mapped_column(
        Float, nullable=False, default=DEFAULT_ACTIVE_AREA[1]
    )
    active_area_y_min: Mapped[float] = mapped_column(
        Float, nullable=False, default=DEFAULT_ACTIVE_AREA[0]
    )
    active_area_y_max: Mapped[float] = mapped_column(
        Float, nullable=False, default=DEFAULT_ACTIVE_AREA[1]
    )
    click_threshold_high: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)
    click_threshold_low: Mapped[float] = mapped_column(Float, nullable=False, default=0.4)

    # Camera identity only; live frame lives on the camera adapter.
    camera_id: Mapped[str] = mapped_column(String, nullable=False, default="0")
    camera_name: Mapped[str] = mapped_column(String, nullable=False, default="")

    click_interfaces: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    microphone_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    microphone_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Flattened DwellSettings.
    dwell_time_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_DWELL_TIME_MS
    )
    dwell_radius_px: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_DWELL_RADIUS_PX
    )
    dwell_palette_opacity: Mapped[float] = mapped_column(
        Float, nullable=False, default=DEFAULT_PALETTE_OPACITY
    )
    dwell_palette_orientation: Mapped[str] = mapped_column(
        String, nullable=False, default=PaletteOrientation.VERTICAL.value
    )


def _active_area_from_row(min_value: float, max_value: float) -> tuple[float, float]:
    area = (float(min_value), float(max_value))
    if area == LEGACY_DEFAULT_ACTIVE_AREA:
        return DEFAULT_ACTIVE_AREA
    return area


def _row_to_domain(row: ProfileRow) -> Profile:
    camera = Camera(
        name=row.camera_name,
        id=row.camera_id,
        fps=0.0,
        current_frame=_PLACEHOLDER_FRAME.copy(),
        frame_width=0,
        frame_height=0,
    )
    settings = FaceTrackerSettings(
        camera=camera,
        speed=row.speed,
        acceleration=row.acceleration,
        sensitivity=(row.sensitivity_x, row.sensitivity_y),
        smoothness=row.smoothness,
        deadzone_radius_px=row.deadzone_radius_px,
        active_area_x=_active_area_from_row(
            row.active_area_x_min, row.active_area_x_max
        ),
        active_area_y=_active_area_from_row(
            row.active_area_y_min, row.active_area_y_max
        ),
        click_threshold_high=row.click_threshold_high,
        click_threshold_low=row.click_threshold_low,
    )
    click_interfaces = {}
    for key, value in (row.click_interfaces or {}).items():
        try:
            click_interfaces[ClickInterface(key)] = bool(value)
        except ValueError:
            # Ignore unknown click interface keys rather than failing load.
            continue
    try:
        orientation = PaletteOrientation(row.dwell_palette_orientation)
    except ValueError:
        orientation = PaletteOrientation.VERTICAL
    return Profile(
        profile_id=row.profile_id,
        name=row.name,
        face_tracker_settings=settings,
        is_active=row.is_active,
        tracking_enabled=bool(row.tracking_enabled),
        click_interfaces=click_interfaces,
        microphone=(
            Microphone(row.microphone_id, row.microphone_name or "")
            if row.microphone_id is not None
            else None
        ),
        dwell_settings=DwellSettings(
            dwell_time_ms=int(row.dwell_time_ms),
            radius_px=int(row.dwell_radius_px),
            palette_opacity=float(row.dwell_palette_opacity),
            palette_orientation=orientation,
        ),
    )


def _apply_domain_to_row(row: ProfileRow, profile: Profile) -> None:
    settings = profile.face_tracker_settings
    row.name = profile.name
    row.is_active = profile.is_active
    row.tracking_enabled = bool(profile.tracking_enabled)
    row.speed = float(settings.speed)
    row.acceleration = float(settings.acceleration)
    sensitivity = tuple(settings.sensitivity)
    row.sensitivity_x = float(sensitivity[0])
    row.sensitivity_y = float(sensitivity[1])
    row.smoothness = float(settings.smoothness)
    row.deadzone_radius_px = int(settings.deadzone_radius_px)
    ax_min, ax_max = settings.active_area_x
    ay_min, ay_max = settings.active_area_y
    row.active_area_x_min = float(ax_min)
    row.active_area_x_max = float(ax_max)
    row.active_area_y_min = float(ay_min)
    row.active_area_y_max = float(ay_max)
    row.click_threshold_high = float(settings.click_threshold_high)
    row.click_threshold_low = float(settings.click_threshold_low)
    row.camera_id = str(settings.camera.id)
    row.camera_name = settings.camera.name
    row.click_interfaces = {
        (k.value if isinstance(k, ClickInterface) else str(k)): bool(v)
        for k, v in (profile.click_interfaces or {}).items()
    }
    row.microphone_id = profile.microphone.id if profile.microphone else None
    row.microphone_name = profile.microphone.name if profile.microphone else None
    dwell = profile.dwell_settings
    row.dwell_time_ms = int(dwell.dwell_time_ms)
    row.dwell_radius_px = int(dwell.radius_px)
    row.dwell_palette_opacity = float(dwell.palette_opacity)
    row.dwell_palette_orientation = dwell.palette_orientation.value


def _new_row_from_domain(profile: Profile) -> ProfileRow:
    row = ProfileRow()
    _apply_domain_to_row(row, profile)
    if profile.profile_id:
        row.profile_id = profile.profile_id
    return row


def _build_engine(db_url: Optional[str]) -> Engine:
    if db_url is None:
        _DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{_DEFAULT_DB_PATH}"
    return create_engine(db_url, future=True)


class SqlAlchemyProfileManager(ProfileManager):
    """ProfileManager backed by SQLAlchemy + SQLite."""

    def __init__(self, db_url: Optional[str] = None, *, reset_db: bool = False):
        self._engine = _build_engine(db_url)
        if reset_db:
            _Base.metadata.drop_all(self._engine)
        _Base.metadata.create_all(self._engine)
        self._upgrade_microphone_schema()
        self._upgrade_dwell_schema()
        self._upgrade_legacy_tracking_defaults()
        with self._engine.begin() as connection:
            version = connection.execute(text("PRAGMA user_version")).scalar_one()
            if version < _MICROPHONE_MIGRATION_VERSION:
                connection.execute(
                    text(f"PRAGMA user_version = {_MICROPHONE_MIGRATION_VERSION}")
                )
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False, future=True)

    # -- helpers -------------------------------------------------------

    def _session(self) -> Session:
        return self._session_factory()

    def _upgrade_microphone_schema(self) -> None:
        """Add nullable voice columns before any ORM query of legacy tables."""
        with self._engine.begin() as connection:
            columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(profiles)"))
            }
            if "microphone_id" not in columns:
                connection.execute(text("ALTER TABLE profiles ADD COLUMN microphone_id VARCHAR"))
            if "microphone_name" not in columns:
                connection.execute(text("ALTER TABLE profiles ADD COLUMN microphone_name VARCHAR"))

    def _upgrade_dwell_schema(self) -> None:
        """Add dwell columns (with defaults) to legacy tables additively."""
        new_columns = {
            "dwell_time_ms": f"INTEGER NOT NULL DEFAULT {DEFAULT_DWELL_TIME_MS}",
            "dwell_radius_px": f"INTEGER NOT NULL DEFAULT {DEFAULT_DWELL_RADIUS_PX}",
            "dwell_palette_opacity": f"FLOAT NOT NULL DEFAULT {DEFAULT_PALETTE_OPACITY}",
            "dwell_palette_orientation": (
                f"VARCHAR NOT NULL DEFAULT '{PaletteOrientation.VERTICAL.value}'"
            ),
            # Tracking became optional alongside dwell; piggyback on the same
            # additive upgrade pass.
            "tracking_enabled": "BOOLEAN NOT NULL DEFAULT 1",
        }
        with self._engine.begin() as connection:
            columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(profiles)"))
            }
            for name, definition in new_columns.items():
                if name not in columns:
                    connection.execute(
                        text(f"ALTER TABLE profiles ADD COLUMN {name} {definition}")
                    )

    def _upgrade_legacy_tracking_defaults(self) -> None:
        """Apply the new tracking defaults to profiles still on old defaults."""
        with Session(self._engine) as session:
            version = session.execute(text("PRAGMA user_version")).scalar_one()
            if version >= _TRACKING_DEFAULTS_MIGRATION_VERSION:
                return

            changed = False
            rows: Iterable[ProfileRow] = session.scalars(select(ProfileRow)).all()
            for row in rows:
                if row.speed in _LEGACY_DEFAULT_TRACKING_SPEEDS:
                    row.speed = DEFAULT_TRACKING_SPEED
                    changed = True
                if row.acceleration in _LEGACY_DEFAULT_TRACKING_ACCELERATIONS:
                    row.acceleration = DEFAULT_TRACKING_ACCELERATION
                    changed = True
            session.execute(
                text(f"PRAGMA user_version = {_TRACKING_DEFAULTS_MIGRATION_VERSION}")
            )
            if changed:
                session.flush()
            session.commit()

    @staticmethod
    def _clear_active_flag(session: Session, except_id: Optional[int]) -> None:
        stmt = select(ProfileRow).where(ProfileRow.is_active.is_(True))
        for row in session.scalars(stmt).all():
            if except_id is not None and row.profile_id == except_id:
                continue
            row.is_active = False

    # -- ProfileManager API --------------------------------------------

    def create_profile(self, profile: Profile) -> Profile:
        with self._session() as session:
            row = _new_row_from_domain(profile)
            if row.is_active:
                self._clear_active_flag(session, except_id=None)
            session.add(row)
            session.commit()
            session.refresh(row)
            profile.profile_id = row.profile_id
            return _row_to_domain(row)

    def list_profiles(self) -> List[Profile]:
        with self._session() as session:
            rows: Iterable[ProfileRow] = session.scalars(select(ProfileRow)).all()
            return [_row_to_domain(r) for r in rows]

    def get_active_profile(self) -> Profile:
        with self._session() as session:
            row = session.scalars(
                select(ProfileRow).where(ProfileRow.is_active.is_(True))
            ).first()
            if row is None:
                raise LookupError("No active profile found")
            return _row_to_domain(row)

    def get_profile(self, profile_id: str) -> Profile:
        pid = int(profile_id)
        with self._session() as session:
            row = session.get(ProfileRow, pid)
            if row is None:
                raise LookupError(f"Profile {profile_id} not found")
            return _row_to_domain(row)

    def delete_profile(self, profile_id) -> None:
        pid = int(profile_id)
        with self._session() as session:
            row = session.get(ProfileRow, pid)
            if row is None:
                raise LookupError(f"Profile {profile_id} not found")
            session.delete(row)
            session.commit()

    def update_profile(self, profile_id, profile: Profile) -> Profile:
        pid = int(profile_id)
        with self._session() as session:
            row = session.get(ProfileRow, pid)
            if row is None:
                raise LookupError(f"Profile {profile_id} not found")
            _apply_domain_to_row(row, profile)
            if row.is_active:
                self._clear_active_flag(session, except_id=pid)
            session.commit()
            session.refresh(row)
            return _row_to_domain(row)

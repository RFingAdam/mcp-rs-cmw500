"""Per-unit bench profile: one portable file per physical CMW500.

Captures everything that differs between one unit/bench and another — connection,
safety limits, the RF routing map (which connector each technology uses), external
attenuation per path (cabling / OTA path loss), a band-preset pointer, and the
expected installed licenses. Loading a profile reconciles the settings singleton;
tools consult the active profile for defaults only when an explicit argument is
absent (explicit always wins), so existing call sites are unaffected.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .safety.validators import SafetyLimits

logger = logging.getLogger(__name__)


class ConnectionProfile(BaseModel):
    """Connection settings for a unit."""

    host: str = "127.0.0.1"
    port: int = 5025
    connection_timeout: float = 5.0
    command_timeout: float = 30.0


class SafetyProfile(BaseModel):
    """Safety clamps for a unit (mirrors safety.validators.SafetyLimits)."""

    max_generator_power_dbm: float = 0.0
    min_generator_power_dbm: float = -130.0
    max_expected_power_dbm: float = 33.0
    max_frequency_hz: float = 6e9
    min_frequency_hz: float = 70e6

    def to_safety_limits(self) -> SafetyLimits:
        return SafetyLimits(
            max_generator_power_dbm=self.max_generator_power_dbm,
            min_generator_power_dbm=self.min_generator_power_dbm,
            max_expected_power_dbm=self.max_expected_power_dbm,
            max_frequency_hz=self.max_frequency_hz,
            min_frequency_hz=self.min_frequency_hz,
        )


class BenchProfile(BaseModel):
    """A complete per-unit bench description.

    routing maps a subsystem key (e.g. ``lte_signaling``, ``ble_signaling``,
    ``wlan_signaling``, ``gprf_gen``, ``gprf_meas``) to an RF connector label
    (e.g. ``RF1COM``). attenuation_db maps a path key (same keys) to external
    attenuation in dB (cabling or OTA path loss). expected_licenses is
    informational — the truth is read live via ``cmw_query_options`` / *OPT?.
    """

    name: str
    description: str = ""
    connection: ConnectionProfile = Field(default_factory=ConnectionProfile)
    safety: SafetyProfile = Field(default_factory=SafetyProfile)
    routing: dict[str, str] = Field(default_factory=dict)
    attenuation_db: dict[str, float] = Field(default_factory=dict)
    band_presets_file: str = ""
    expected_licenses: list[str] = Field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchProfile:
        return cls.model_validate(data)

    def connector_map(self) -> dict[str, str]:
        """Routing map, for coex.routing.validate_routing."""
        return dict(self.routing)

    def save(self, filepath: str | Path) -> None:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, filepath: str | Path) -> BenchProfile:
        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        return cls.from_dict(data)


# ---------------------------------------------------------------------------
# Active-profile singleton
# ---------------------------------------------------------------------------

_active_profile: BenchProfile | None = None


def get_active_profile() -> BenchProfile | None:
    return _active_profile


def set_active_profile(profile: BenchProfile) -> None:
    global _active_profile
    _active_profile = profile


def clear_active_profile() -> None:
    global _active_profile
    _active_profile = None


def apply_profile_to_settings(profile: BenchProfile) -> None:
    """Reconcile the settings singleton with a profile.

    Safety limits are read when a driver is constructed (in shared._get_cmw), so
    changes here take effect on the *next* connection, not on pooled ones.
    """
    from .config import get_settings

    settings = get_settings()
    settings.default_host = profile.connection.host
    settings.default_port = profile.connection.port
    settings.connection_timeout = profile.connection.connection_timeout
    settings.command_timeout = profile.connection.command_timeout
    settings.max_generator_power_dbm = profile.safety.max_generator_power_dbm
    settings.min_generator_power_dbm = profile.safety.min_generator_power_dbm
    settings.max_expected_power_dbm = profile.safety.max_expected_power_dbm
    settings.max_frequency_hz = profile.safety.max_frequency_hz
    settings.min_frequency_hz = profile.safety.min_frequency_hz
    if profile.band_presets_file:
        settings.band_presets_file = profile.band_presets_file


def load_active_profile(filepath: str | Path) -> BenchProfile:
    """Load a profile file, make it active, and reconcile settings."""
    profile = BenchProfile.load(filepath)
    set_active_profile(profile)
    apply_profile_to_settings(profile)
    logger.info("Loaded bench profile %r from %s", profile.name, filepath)
    return profile


# ---------------------------------------------------------------------------
# Resolver helpers — explicit argument always wins over the active profile.
# ---------------------------------------------------------------------------


def resolve_connector(subsystem: str, explicit: str | None) -> str | None:
    """Connector for a subsystem: explicit arg, else active-profile routing, else None."""
    if explicit:
        return explicit
    profile = get_active_profile()
    return profile.routing.get(subsystem) if profile else None


def resolve_attenuation(path: str, explicit: float | None) -> float | None:
    """External attenuation for a path: explicit arg, else active profile, else None."""
    if explicit is not None:
        return explicit
    profile = get_active_profile()
    return profile.attenuation_db.get(path) if profile else None

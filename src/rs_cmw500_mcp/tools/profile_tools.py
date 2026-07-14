"""Per-unit bench-profile tools: load, show, save, list, and apply."""

import logging
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult, Tool

from ..coex.routing import RoutingError, validate_routing
from ..config import get_settings
from ..profile import (
    BenchProfile,
    apply_profile_to_settings,
    get_active_profile,
    set_active_profile,
)
from ..safety.validators import validate_safe_path
from .registry import registry
from .shared import _format_error, _format_result, _get_cmw

logger = logging.getLogger(__name__)

_RECONNECT_NOTE = (
    "Safety limits/connection from a profile take effect on the NEXT connection; "
    "reconnect (cmw_disconnect then any tool) to apply them to a pooled session."
)

# Subsystems whose routing/attenuation this server will actually push to the
# instrument (well-grounded GPRF ROUTe/attenuation). Everything else is recorded
# as intent only, because signaling ROUTe SCPI is app-note-derived/uncertain.
_GPRF_PUSH = {"gprf_gen": "gen", "gprf_meas": "meas"}


def _profile_path(filename: str) -> Path:
    settings = get_settings()
    safe = Path(filename).name  # strip directory components
    return validate_safe_path(f"{safe}.json", settings.profile_dir)


async def _handle_profile_load(args: dict[str, Any]) -> CallToolResult:
    path = _profile_path(args["filename"])
    if not path.exists():
        return _format_error(FileNotFoundError(f"Profile not found: {path}"))
    profile = BenchProfile.load(path)
    set_active_profile(profile)
    apply_profile_to_settings(profile)
    routing_ok = True
    routing_error = None
    try:
        if profile.routing:
            validate_routing(profile.connector_map())
    except RoutingError as exc:
        routing_ok = False
        routing_error = str(exc)
    return _format_result(
        {
            "status": "ok",
            "loaded_from": str(path),
            "profile": profile.name,
            "routing_valid": routing_ok,
            "routing_error": routing_error,
            "note": _RECONNECT_NOTE,
        }
    )


async def _handle_profile_show(args: dict[str, Any]) -> CallToolResult:
    profile = get_active_profile()
    if profile is None:
        return _format_result({"active": False})
    return _format_result({"active": True, "profile": profile.to_dict()})


async def _handle_profile_save(args: dict[str, Any]) -> CallToolResult:
    profile: BenchProfile | None
    if args.get("profile"):
        profile = BenchProfile.from_dict(args["profile"])
    else:
        profile = get_active_profile()
    if profile is None:
        return _format_error(ValueError("No 'profile' provided and no active profile to save."))
    path = _profile_path(args["filename"])
    profile.save(path)
    return _format_result({"status": "ok", "saved_to": str(path), "profile": profile.name})


async def _handle_profile_list(args: dict[str, Any]) -> CallToolResult:
    settings = get_settings()
    base = Path(settings.profile_dir)
    profiles: list[dict[str, Any]] = []
    if base.exists():
        for filepath in sorted(base.glob("*.json")):
            try:
                p = BenchProfile.load(filepath)
                profiles.append(
                    {"name": p.name, "description": p.description, "file": filepath.stem}
                )
            except (OSError, ValueError) as exc:
                logger.debug("Skipping unreadable profile %s: %s", filepath, exc)
    return _format_result({"profiles": profiles, "count": len(profiles)})


async def _handle_profile_apply(args: dict[str, Any]) -> CallToolResult:
    profile = get_active_profile()
    if profile is None:
        return _format_error(ValueError("No active profile. Load one first (cmw_profile_load)."))
    # Guard against a connector collision before touching the instrument.
    try:
        if profile.routing:
            validate_routing(profile.connector_map())
    except RoutingError as exc:
        return _format_error(exc)

    cmw = await _get_cmw(args.get("host"), args.get("port"))
    pushed: list[str] = []

    # Well-grounded: push GPRF generator/analyzer ports + external attenuation.
    for subsystem, kind in _GPRF_PUSH.items():
        connector = profile.routing.get(subsystem)
        atten = profile.attenuation_db.get(subsystem)
        if connector:
            if kind == "gen":
                await cmw.gen_set_port(connector)
            else:
                await cmw.meas_set_port(connector)
            pushed.append(f"{subsystem} -> {connector}")
        if atten is not None:
            if kind == "gen":
                await cmw.gen_set_external_attenuation(atten)
            else:
                await cmw.meas_set_external_attenuation(atten)
            pushed.append(f"{subsystem} attenuation {atten} dB")

    # Signaling routing is recorded as intent only (SCPI is bench/GUI-applied).
    planned_scpi: list[str] = []
    for subsystem, connector in profile.routing.items():
        if subsystem not in _GPRF_PUSH:
            planned_scpi.append(f"# {subsystem}: route to {connector} (apply on instrument/GUI)")

    return _format_result(
        {
            "status": "ok",
            "pushed": pushed,
            "planned_scpi": planned_scpi,
            "note": (
                "GPRF routing/attenuation applied. Signaling routing is listed as intent "
                "only and must be set on the instrument or via raw SCPI after validation."
            ),
        }
    )


# =============================================================================
# Registration
# =============================================================================

_FILENAME = {"filename": {"type": "string", "description": "Profile filename (no .json)"}}
_HOST_PORT = {"host": {"type": "string"}, "port": {"type": "integer"}}

registry.register(
    Tool(
        name="cmw_profile_load",
        description=(
            "Load a per-unit bench profile JSON and make it active: reconciles "
            "connection/safety settings and validates the RF routing map. Profile "
            "connectors/attenuation then default any tool arg left unset."
        ),
        inputSchema={"type": "object", "properties": {**_FILENAME}, "required": ["filename"]},
    ),
    _handle_profile_load,
)

registry.register(
    Tool(
        name="cmw_profile_show",
        description="Show the currently active bench profile (or active=false).",
        inputSchema={"type": "object", "properties": {}},
    ),
    _handle_profile_show,
)

registry.register(
    Tool(
        name="cmw_profile_save",
        description=(
            "Save a bench profile JSON. Provide 'profile' (full BenchProfile object) "
            "or omit it to save the active profile."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                **_FILENAME,
                "profile": {
                    "type": "object",
                    "description": "Full bench profile object (name, connection, safety, "
                    "routing, attenuation_db, expected_licenses, notes).",
                },
            },
            "required": ["filename"],
        },
    ),
    _handle_profile_save,
)

registry.register(
    Tool(
        name="cmw_profile_list",
        description="List saved bench profiles in the profile directory.",
        inputSchema={"type": "object", "properties": {}},
    ),
    _handle_profile_list,
)

registry.register(
    Tool(
        name="cmw_profile_apply",
        description=(
            "Push the active profile's GPRF routing + external attenuation to the "
            "instrument; return signaling routing as intent (planned_scpi). Validates "
            "connectors first and refuses on a collision."
        ),
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_profile_apply,
)

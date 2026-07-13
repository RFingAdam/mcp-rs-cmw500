"""Coexistence orchestration tools: plan, step, and read a coex sweep.

Exposes the LTE(aggressor) x BLE(victim) desense sweep as a resumable job so a
long run stays interruptible and observable: `cmw_coex_plan` defines the grid,
`cmw_coex_step` advances it a bounded number of points, and `cmw_coex_result`
returns the full matrix + long-format data.
"""

import logging
import uuid
from typing import Any

from mcp.types import CallToolResult, Tool

from ..coex.orchestrator import CoexSweep, VictimSpec, build_lte_ble_plan
from ..coex.routing import RoutingError, validate_routing
from ..config import get_settings
from ..models.band_plans import earfcn_to_frequencies
from .registry import registry
from .shared import _format_error, _format_result, _get_cmw

logger = logging.getLogger(__name__)

# Server-side sweep store, keyed by sweep_id (like the connection pool).
_sweeps: dict[str, CoexSweep] = {}

_HOST_PORT = {"host": {"type": "string"}, "port": {"type": "integer"}}


def _victim_from_args(args: dict[str, Any]) -> VictimSpec:
    return VictimSpec(
        channel_start=int(args.get("ble_channel_start", 1)),
        channel_end=int(args.get("ble_channel_end", 38)),
        channel_spacing=int(args.get("ble_channel_spacing", 1)),
        packets=int(args.get("ble_packets", 100)),
        start_power_dbm=float(args.get("ble_start_power_dbm", -50.0)),
        coarse_step_db=float(args.get("ble_coarse_step_db", 5.0)),
        fine_step_db=float(args.get("ble_fine_step_db", 1.0)),
        target_per_pct=float(args.get("ble_target_per_pct", 10.0)),
        max_tx_dbm=float(args.get("ble_max_tx_dbm", -30.0)),
    )


async def _handle_coex_validate_routing(args: dict[str, Any]) -> CallToolResult:
    connectors = args.get("connectors") or {}
    try:
        validate_routing(connectors)
    except RoutingError as exc:
        return _format_error(exc)
    return _format_result({"status": "ok", "connectors": connectors})


async def _handle_coex_plan(args: dict[str, Any]) -> CallToolResult:
    settings = get_settings()
    host = args.get("host") or settings.default_host
    port = int(args.get("port") or settings.default_port)

    victim = _victim_from_args(args)
    plan = build_lte_ble_plan(
        lte_bands=[int(b) for b in args.get("lte_bands", [])],
        earfcn_spacing=int(args.get("earfcn_spacing", 25)),
        victim=victim,
        include_baseline=bool(args.get("include_baseline", True)),
    )
    if plan.total_points == 0:
        return _format_error(
            ValueError("Empty sweep: provide lte_bands and/or include_baseline=true.")
        )

    sweep_id = uuid.uuid4().hex[:12]
    _sweeps[sweep_id] = CoexSweep(sweep_id, plan, host, port)
    summary = plan.to_dict()
    # Trim the potentially long condition list in the plan echo.
    preview = summary["conditions"][:8]
    return _format_result(
        {
            "sweep_id": sweep_id,
            "total_points": plan.total_points,
            "condition_count": len(plan.conditions),
            "channel_count": len(plan.channels),
            "conditions_preview": preview,
            "victim": summary["victim"],
        }
    )


async def _handle_coex_step(args: dict[str, Any]) -> CallToolResult:
    sweep = _sweeps.get(args.get("sweep_id", ""))
    if sweep is None:
        return _format_error(ValueError(f"Unknown sweep_id: {args.get('sweep_id')!r}"))
    cmw = await _get_cmw(sweep.host, sweep.port)
    result = await sweep.step(cmw, max_points=int(args.get("max_points", 1)))
    return _format_result(result)


async def _handle_coex_result(args: dict[str, Any]) -> CallToolResult:
    sweep = _sweeps.get(args.get("sweep_id", ""))
    if sweep is None:
        return _format_error(ValueError(f"Unknown sweep_id: {args.get('sweep_id')!r}"))
    return _format_result(sweep.result(include_long=bool(args.get("include_long", True))))


async def _handle_coex_measure_point(args: dict[str, Any]) -> CallToolResult:
    """Ad-hoc single condition: optionally apply an LTE aggressor, then measure
    BLE sensitivity on one channel."""
    from .bluetooth_signaling import run_ble_rx_sensitivity
    from .lte_rx import wait_for_lte_attach

    cmw = await _get_cmw(args.get("host"), args.get("port"))
    condition: dict[str, Any] = {"technology": "NONE"}

    band = args.get("lte_band")
    earfcn = args.get("lte_earfcn")
    if band is not None and earfcn is not None:
        await cmw.lte_set_operating_band(int(band))
        await cmw.lte_set_earfcn(int(earfcn), "DL")
        state = ""
        try:
            state = (await cmw.lte_ps_state()).strip()
        except Exception:  # noqa: BLE001
            state = ""
        if "ATT" not in state:
            attached, state = await wait_for_lte_attach(cmw)
        _b, dl, ul = earfcn_to_frequencies(int(earfcn))
        condition = {
            "technology": "LTE",
            "band": int(band),
            "earfcn": int(earfcn),
            "dl_mhz": dl,
            "ul_mhz": ul,
            "attached_state": state,
        }

    await cmw.ble_sig_clear()
    await cmw.ble_sig_set_packets(int(args.get("ble_packets", 100)))
    result = await run_ble_rx_sensitivity(
        cmw,
        channel=int(args["ble_channel"]),
        start_power_dbm=float(args.get("ble_start_power_dbm", -50.0)),
    )
    return _format_result({"aggressor": condition, "victim": result.to_dict()})


# =============================================================================
# Registration
# =============================================================================

registry.register(
    Tool(
        name="cmw_coex_validate_routing",
        description=(
            "Check that each technology is assigned a distinct RF connector before "
            "a coex run. Pure check - does not configure instrument routing."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "connectors": {
                    "type": "object",
                    "description": "subsystem -> connector, e.g. {'lte':'RF1COM'}",
                    "additionalProperties": {"type": "string"},
                }
            },
            "required": ["connectors"],
        },
    ),
    _handle_coex_validate_routing,
)

registry.register(
    Tool(
        name="cmw_coex_plan",
        description=(
            "Define an LTE(aggressor) x BLE(victim) desense sweep and return a "
            "sweep_id. Expands LTE bands x EARFCNs (plus an optional aggressor-off "
            "baseline) against BLE channels. Then call cmw_coex_step repeatedly."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "lte_bands": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "LTE aggressor bands to sweep (e.g. [7, 20]).",
                },
                "earfcn_spacing": {"type": "integer", "default": 25},
                "include_baseline": {
                    "type": "boolean",
                    "description": "Prepend an aggressor-off baseline condition (default true).",
                    "default": True,
                },
                "ble_channel_start": {"type": "integer", "default": 1},
                "ble_channel_end": {"type": "integer", "default": 38},
                "ble_channel_spacing": {"type": "integer", "default": 1},
                "ble_packets": {"type": "integer", "default": 100},
                "ble_start_power_dbm": {"type": "number", "default": -50},
                "ble_coarse_step_db": {"type": "number", "default": 5.0},
                "ble_fine_step_db": {"type": "number", "default": 1.0},
                "ble_target_per_pct": {"type": "number", "default": 10.0},
                "ble_max_tx_dbm": {"type": "number", "default": -30},
                **_HOST_PORT,
            },
        },
    ),
    _handle_coex_plan,
)

registry.register(
    Tool(
        name="cmw_coex_step",
        description=(
            "Run the next N measurement points of a coex sweep (default 1). Returns "
            "progress + the partial matrix so a long run stays observable."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sweep_id": {"type": "string"},
                "max_points": {"type": "integer", "default": 1},
            },
            "required": ["sweep_id"],
        },
    ),
    _handle_coex_step,
)

registry.register(
    Tool(
        name="cmw_coex_result",
        description="Return the full coex sweep result: matrix + long-format rows.",
        inputSchema={
            "type": "object",
            "properties": {
                "sweep_id": {"type": "string"},
                "include_long": {"type": "boolean", "default": True},
            },
            "required": ["sweep_id"],
        },
    ),
    _handle_coex_result,
)

registry.register(
    Tool(
        name="cmw_coex_measure_point",
        description=(
            "Measure BLE receiver sensitivity on one channel, optionally with an LTE "
            "aggressor (band + EARFCN) applied first. Ad-hoc single-point coex probe."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ble_channel": {"type": "integer", "description": "BLE data channel (0-39)"},
                "lte_band": {"type": "integer", "description": "Optional LTE aggressor band"},
                "lte_earfcn": {"type": "integer", "description": "Optional LTE aggressor EARFCN"},
                "ble_packets": {"type": "integer", "default": 100},
                "ble_start_power_dbm": {"type": "number", "default": -50},
                **_HOST_PORT,
            },
            "required": ["ble_channel"],
        },
    ),
    _handle_coex_measure_point,
)

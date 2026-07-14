"""BLE signaling receiver-PER tools for the CMW500.

The existing ``bluetooth`` module covers non-signaling (BLUetooth:MEAS) TX
measurements. This module adds the signaling (BLUetooth:SIGN) receiver path:
connect/detach control, single PER measurements, and a coarse+fine PER
sensitivity search. Reusable coroutines are imported by the coex orchestrator.
"""

import asyncio
import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from ..driver.cmw500_driver import CMW500Driver
from ..driver.search import descend_to_threshold
from ..models.band_plans import ble_channel_to_freq_mhz
from ..models.cmw_types import RxSensitivityResult
from .registry import registry
from .shared import _format_result, _get_cmw

logger = logging.getLogger(__name__)

DEFAULT_SETTLE_S = 0.12


async def measure_ble_per(
    cmw: CMW500Driver, level_dbm: float, settle_s: float = DEFAULT_SETTLE_S
) -> float | None:
    """Set the CMW BLE TX level, read PER, return PER% (or None if invalid/drop)."""
    await cmw.ble_sig_set_level(level_dbm)
    if settle_s > 0:
        await asyncio.sleep(settle_s)
    result = await cmw.ble_sig_read_per()
    return result.per_percent if result.valid else None


async def recover_ble_link(
    cmw: CMW500Driver,
    probe_power_dbm: float,
    boost_power_dbm: float,
    max_attempts: int = 3,
    settle_s: float = DEFAULT_SETTLE_S,
    wait_s: float = 10.0,
) -> bool:
    """Attempt to re-establish a dropped BLE link (boost power -> CONN, then DET/CONN)."""
    for attempt in range(1, max_attempts + 1):
        await cmw.ble_sig_set_level(boost_power_dbm)
        if attempt >= 2:
            await cmw.ble_sig_connection("DET")
            await asyncio.sleep(settle_s)
            await cmw.ble_sig_connection("CONN")
        else:
            await cmw.ble_sig_connection("CONN")
        await asyncio.sleep(wait_s)
        if await measure_ble_per(cmw, probe_power_dbm, settle_s) is not None:
            return True
    return False


async def run_ble_rx_sensitivity(
    cmw: CMW500Driver,
    channel: int,
    start_power_dbm: float = -50.0,
    coarse_step: float = 5.0,
    fine_step: float = 1.0,
    target_pct: float = 10.0,
    max_tx_dbm: float = -30.0,
    level_floor: float | None = None,
    settle_s: float = DEFAULT_SETTLE_S,
) -> RxSensitivityResult:
    """Find BLE receiver sensitivity (PER) at one data channel.

    Descends the CMW TX level to the lowest power the DUT still receives below
    the target PER. If the start level is too weak, TX is raised toward
    ``max_tx_dbm`` first (``ascend_first``), mirroring the validated script's
    "raise TX until it works" behaviour.
    """
    await cmw.ble_sig_set_channel(channel)

    async def measure(level: float) -> float | None:
        return await measure_ble_per(cmw, level, settle_s)

    search = await descend_to_threshold(
        measure,
        start_level=start_power_dbm,
        coarse_step=coarse_step,
        fine_step=fine_step,
        target_pct=target_pct,
        level_floor=level_floor,
        level_ceiling=max_tx_dbm,
        ascend_first=True,
    )
    return RxSensitivityResult(
        technology="BLE-PER",
        status=search.status,
        sensitivity_dbm=search.threshold_level,
        target_pct=target_pct,
        channel=channel,
        frequency_mhz=ble_channel_to_freq_mhz(channel),
        points_measured=len(search.trace),
        trace=[p.to_dict() for p in search.trace],
    )


# =============================================================================
# Handlers
# =============================================================================


async def _handle_ble_sig_configure(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    packets = int(args.get("packets", 100))
    await cmw.ble_sig_clear()
    await cmw.ble_sig_set_packets(packets)
    return _format_result({"status": "ok", "packets": packets})


async def _handle_ble_sig_connect(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.ble_sig_connection("CONN")
    return _format_result({"status": "ok", "action": "CONN"})


async def _handle_ble_sig_detach(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.ble_sig_connection("DET")
    return _format_result({"status": "ok", "action": "DET"})


async def _handle_ble_sig_measure_per(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    channel = int(args["channel"])
    await cmw.ble_sig_set_channel(channel)
    per = await measure_ble_per(
        cmw, float(args["level_dbm"]), float(args.get("settle_s", DEFAULT_SETTLE_S))
    )
    return _format_result(
        {
            "channel": channel,
            "frequency_mhz": ble_channel_to_freq_mhz(channel),
            "level_dbm": float(args["level_dbm"]),
            "per_percent": per,
            "valid": per is not None,
        }
    )


async def _handle_ble_sig_sensitivity(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await run_ble_rx_sensitivity(
        cmw,
        channel=int(args["channel"]),
        start_power_dbm=float(args.get("start_power_dbm", -50.0)),
        coarse_step=float(args.get("coarse_step_db", 5.0)),
        fine_step=float(args.get("fine_step_db", 1.0)),
        target_pct=float(args.get("target_per_pct", 10.0)),
        max_tx_dbm=float(args.get("max_tx_dbm", -30.0)),
    )
    return _format_result(result.to_dict())


# =============================================================================
# Registration
# =============================================================================

_HOST_PORT = {"host": {"type": "string"}, "port": {"type": "integer"}}

registry.register(
    Tool(
        name="cmw_ble_sig_configure",
        description=(
            "Configure the BLE signaling PER measurement (clear queue + set packet "
            "count per LE 1M measurement). Requires the CMW BLE signaling app running "
            "as Central with an established connection to the DUT."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "packets": {"type": "integer", "default": 100},
                **_HOST_PORT,
            },
        },
    ),
    _handle_ble_sig_configure,
)

registry.register(
    Tool(
        name="cmw_ble_sig_connect",
        description="Connect the BLE signaling link (CALL ... CONN).",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_ble_sig_connect,
)

registry.register(
    Tool(
        name="cmw_ble_sig_detach",
        description="Detach the BLE signaling link (CALL ... DET).",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_ble_sig_detach,
)

registry.register(
    Tool(
        name="cmw_ble_sig_measure_per",
        description=(
            "Set BLE data channel + CMW TX level and read one LE 1M PER result "
            "(percent). Returns valid=false if the link dropped or the read was invalid."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "channel": {"type": "integer", "description": "BLE data channel (0-39)"},
                "level_dbm": {"type": "number", "description": "CMW BLE TX level (dBm)"},
                "settle_s": {"type": "number", "default": 0.12},
                **_HOST_PORT,
            },
            "required": ["channel", "level_dbm"],
        },
    ),
    _handle_ble_sig_measure_per,
)

registry.register(
    Tool(
        name="cmw_ble_sig_sensitivity",
        description=(
            "Find BLE receiver sensitivity at one data channel: a coarse+fine search "
            "for the lowest CMW TX level meeting the target PER (default 10%)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "channel": {"type": "integer", "description": "BLE data channel (0-39)"},
                "start_power_dbm": {"type": "number", "default": -50},
                "coarse_step_db": {"type": "number", "default": 5.0},
                "fine_step_db": {"type": "number", "default": 1.0},
                "target_per_pct": {"type": "number", "default": 10.0},
                "max_tx_dbm": {
                    "type": "number",
                    "description": "Highest TX level to try when raising power (default -30)",
                    "default": -30,
                },
                **_HOST_PORT,
            },
            "required": ["channel"],
        },
    ),
    _handle_ble_sig_sensitivity,
)

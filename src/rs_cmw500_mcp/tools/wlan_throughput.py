"""WLAN throughput (DAU) tools: IP throughput, iPerf, ping.

Requires DAU hardware (CMW-B450) + option KM050, and typically the WLAN signaling
AP (cmw_wlan_sig_*) with the DUT associated. This provides the victim metric for
LTE+Wi-Fi coexistence (throughput under an LTE aggressor). THRoughput commands
are well-grounded; iPerf/ping are simplified — validate on hardware.
"""

import asyncio
import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from ..driver.cmw500_driver import CMW500Driver
from ..models.cmw_types import ThroughputResult
from .registry import registry
from .shared import _format_result, _get_cmw

logger = logging.getLogger(__name__)

_HOST_PORT = {"host": {"type": "string"}, "port": {"type": "integer"}}


async def run_wlan_throughput(
    cmw: CMW500Driver, direction: str = "DL", settle_s: float = 1.0, init: bool = True
) -> ThroughputResult:
    """Start (optional) and fetch overall IP throughput in one direction."""
    if init:
        await cmw.data_throughput_init()
        if settle_s > 0:
            await asyncio.sleep(settle_s)
    return await cmw.data_throughput_fetch(direction)


async def _handle_data_throughput(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await run_wlan_throughput(
        cmw,
        direction=args.get("direction", "DL"),
        settle_s=float(args.get("settle_s", 1.0)),
        init=bool(args.get("init", True)),
    )
    return _format_result(result.to_dict())


async def _handle_data_iperf_run(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    protocol = args.get("protocol", "TCP")
    duration = int(args.get("duration_s", 10))
    await cmw.data_iperf_configure(
        protocol=protocol, duration_s=duration, parallel=int(args.get("parallel", 1))
    )
    await cmw.data_iperf_init()
    await asyncio.sleep(min(float(duration), 30.0))
    result = await cmw.data_iperf_fetch()
    return _format_result({"protocol": protocol, "duration_s": duration, **result})


async def _handle_data_ping(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.data_ping(args["destination"], count=int(args.get("count", 10)))
    return _format_result(result)


# =============================================================================
# Registration
# =============================================================================

registry.register(
    Tool(
        name="cmw_data_throughput",
        description=(
            "Measure DAU overall IP throughput (bit/s) in one direction (DL/UL). "
            "The Wi-Fi victim metric for LTE+Wi-Fi coex. Requires DAU (CMW-B450/KM050)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["DL", "UL"], "default": "DL"},
                "init": {"type": "boolean", "default": True},
                "settle_s": {"type": "number", "default": 1.0},
                **_HOST_PORT,
            },
        },
    ),
    _handle_data_throughput,
)

registry.register(
    Tool(
        name="cmw_data_iperf_run",
        description=(
            "Configure + run a DAU iPerf measurement and fetch results (TCP/UDP). "
            "Simplified command set - validate on hardware."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "protocol": {"type": "string", "enum": ["TCP", "UDP"], "default": "TCP"},
                "duration_s": {"type": "integer", "default": 10},
                "parallel": {"type": "integer", "default": 1},
                **_HOST_PORT,
            },
        },
    ),
    _handle_data_iperf_run,
)

registry.register(
    Tool(
        name="cmw_data_ping",
        description="Run a DAU ping to a destination IP and fetch the result.",
        inputSchema={
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Destination IP address"},
                "count": {"type": "integer", "default": 10},
                **_HOST_PORT,
            },
            "required": ["destination"],
        },
    ),
    _handle_data_ping,
)

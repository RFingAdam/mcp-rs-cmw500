"""WLAN non-signaling measurement tools for CMW500."""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from ..models.cmw_types import WLANBandwidth, WLANMeasConfig, WLANStandard
from .registry import registry
from .shared import _format_result, _get_cmw

logger = logging.getLogger(__name__)


# =============================================================================
# Handlers
# =============================================================================


async def _handle_wlan_configure(args: dict[str, Any]) -> CallToolResult:
    """Configure WLAN measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    config = WLANMeasConfig(
        standard=WLANStandard(args.get("standard", "AX")),
        bandwidth=WLANBandwidth(args.get("bandwidth", "BW80")),
        frequency_hz=args.get("frequency_hz", 5.18e9),
        expected_power_dbm=args.get("expected_power_dbm", 20.0),
        meas_instance=args.get("meas_instance", 1),
    )
    await cmw.wlan_configure(config)
    return _format_result({"status": "ok", "wlan_config": config.to_dict()})


async def _handle_wlan_set_standard(args: dict[str, Any]) -> CallToolResult:
    """Set WLAN standard."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    standard = args["standard"]
    n = args.get("meas_instance", 1)
    await cmw.wlan_set_standard(standard, n)
    return _format_result({"status": "ok", "standard": standard})


async def _handle_wlan_set_bandwidth(args: dict[str, Any]) -> CallToolResult:
    """Set WLAN bandwidth."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    bandwidth = args["bandwidth"]
    n = args.get("meas_instance", 1)
    await cmw.wlan_set_bandwidth(bandwidth, n)
    return _format_result({"status": "ok", "bandwidth": bandwidth})


async def _handle_wlan_set_frequency(args: dict[str, Any]) -> CallToolResult:
    """Set WLAN frequency."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    freq = args["frequency_hz"]
    n = args.get("meas_instance", 1)
    await cmw.wlan_set_frequency(freq, n)
    return _format_result({"status": "ok", "frequency_hz": freq})


async def _handle_wlan_set_expected_power(args: dict[str, Any]) -> CallToolResult:
    """Set WLAN expected power."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    power = args["power_dbm"]
    n = args.get("meas_instance", 1)
    await cmw.wlan_set_expected_power(power, n)
    return _format_result({"status": "ok", "expected_power_dbm": power})


async def _handle_wlan_trigger(args: dict[str, Any]) -> CallToolResult:
    """Trigger WLAN measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    n = args.get("meas_instance", 1)
    await cmw.wlan_trigger(n)
    return _format_result({"status": "ok", "measurement": "wlan_meval_triggered"})


async def _handle_wlan_fetch_power(args: dict[str, Any]) -> CallToolResult:
    """Fetch WLAN power."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    n = args.get("meas_instance", 1)
    result = await cmw.wlan_fetch_power(n)
    return _format_result(result)


async def _handle_wlan_fetch_evm(args: dict[str, Any]) -> CallToolResult:
    """Fetch WLAN EVM."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    n = args.get("meas_instance", 1)
    result = await cmw.wlan_fetch_evm(n)
    return _format_result(result)


async def _handle_wlan_fetch_spectrum_flatness(
    args: dict[str, Any],
) -> CallToolResult:
    """Fetch WLAN spectrum flatness."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    n = args.get("meas_instance", 1)
    result = await cmw.wlan_fetch_spectrum_flatness(n)
    return _format_result(result)


async def _handle_wlan_fetch_frequency_error(
    args: dict[str, Any],
) -> CallToolResult:
    """Fetch WLAN frequency error."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    n = args.get("meas_instance", 1)
    result = await cmw.wlan_fetch_frequency_error(n)
    return _format_result(result)


async def _handle_wlan_fetch_all(args: dict[str, Any]) -> CallToolResult:
    """Fetch all WLAN measurements."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    n = args.get("meas_instance", 1)
    result = await cmw.wlan_fetch_all(n)
    return _format_result(result)


# =============================================================================
# Common schema fragment for meas_instance
# =============================================================================

_MEAS_INSTANCE_PROP = {
    "meas_instance": {
        "type": "integer",
        "description": "Measurement instance (default: 1)",
        "default": 1,
    },
}

_HOST_PORT_PROPS = {
    "host": {"type": "string"},
    "port": {"type": "integer"},
}


def _props(*extra_dicts: dict[str, Any]) -> dict[str, Any]:
    """Merge property dicts."""
    merged: dict[str, Any] = {}
    for d in extra_dicts:
        merged.update(d)
    merged.update(_MEAS_INSTANCE_PROP)
    merged.update(_HOST_PORT_PROPS)
    return merged


# =============================================================================
# Registration
# =============================================================================

registry.register(
    Tool(
        name="cmw_wlan_configure",
        description="Configure WLAN non-signaling measurement (standard, BW, freq, power)",
        inputSchema={
            "type": "object",
            "properties": _props(
                {
                    "standard": {
                        "type": "string",
                        "description": "WLAN standard",
                        "enum": ["A", "B", "G", "N", "AC", "AX"],
                        "default": "AX",
                    },
                    "bandwidth": {
                        "type": "string",
                        "description": "Channel bandwidth",
                        "enum": ["BW20", "BW40", "BW80", "BW160"],
                        "default": "BW80",
                    },
                    "frequency_hz": {
                        "type": "number",
                        "description": "Frequency in Hz (default: 5.18 GHz)",
                        "default": 5.18e9,
                    },
                    "expected_power_dbm": {
                        "type": "number",
                        "description": "Expected power in dBm (default: 20)",
                        "default": 20.0,
                    },
                }
            ),
        },
    ),
    _handle_wlan_configure,
)

registry.register(
    Tool(
        name="cmw_wlan_set_standard",
        description="Set WLAN 802.11 standard (A/B/G/N/AC/AX)",
        inputSchema={
            "type": "object",
            "properties": _props(
                {
                    "standard": {
                        "type": "string",
                        "description": "WLAN standard",
                        "enum": ["A", "B", "G", "N", "AC", "AX"],
                    },
                }
            ),
            "required": ["standard"],
        },
    ),
    _handle_wlan_set_standard,
)

registry.register(
    Tool(
        name="cmw_wlan_set_bandwidth",
        description="Set WLAN channel bandwidth (20/40/80/160 MHz)",
        inputSchema={
            "type": "object",
            "properties": _props(
                {
                    "bandwidth": {
                        "type": "string",
                        "description": "Channel bandwidth",
                        "enum": ["BW20", "BW40", "BW80", "BW160"],
                    },
                }
            ),
            "required": ["bandwidth"],
        },
    ),
    _handle_wlan_set_bandwidth,
)

registry.register(
    Tool(
        name="cmw_wlan_set_frequency",
        description="Set WLAN measurement frequency in Hz",
        inputSchema={
            "type": "object",
            "properties": _props(
                {
                    "frequency_hz": {
                        "type": "number",
                        "description": "Frequency in Hz",
                    },
                }
            ),
            "required": ["frequency_hz"],
        },
    ),
    _handle_wlan_set_frequency,
)

registry.register(
    Tool(
        name="cmw_wlan_set_expected_power",
        description="Set WLAN expected input power in dBm",
        inputSchema={
            "type": "object",
            "properties": _props(
                {
                    "power_dbm": {
                        "type": "number",
                        "description": "Expected power in dBm",
                    },
                }
            ),
            "required": ["power_dbm"],
        },
    ),
    _handle_wlan_set_expected_power,
)

registry.register(
    Tool(
        name="cmw_wlan_trigger",
        description="Trigger WLAN multi-evaluation measurement",
        inputSchema={
            "type": "object",
            "properties": _props({}),
        },
    ),
    _handle_wlan_trigger,
)

registry.register(
    Tool(
        name="cmw_wlan_fetch_power",
        description="Fetch WLAN TX power measurement results",
        inputSchema={
            "type": "object",
            "properties": _props({}),
        },
    ),
    _handle_wlan_fetch_power,
)

registry.register(
    Tool(
        name="cmw_wlan_fetch_evm",
        description="Fetch WLAN EVM (Error Vector Magnitude) measurement results",
        inputSchema={
            "type": "object",
            "properties": _props({}),
        },
    ),
    _handle_wlan_fetch_evm,
)

registry.register(
    Tool(
        name="cmw_wlan_fetch_spectrum_flatness",
        description="Fetch WLAN spectrum flatness measurement results",
        inputSchema={
            "type": "object",
            "properties": _props({}),
        },
    ),
    _handle_wlan_fetch_spectrum_flatness,
)

registry.register(
    Tool(
        name="cmw_wlan_fetch_frequency_error",
        description="Fetch WLAN frequency error measurement results",
        inputSchema={
            "type": "object",
            "properties": _props({}),
        },
    ),
    _handle_wlan_fetch_frequency_error,
)

registry.register(
    Tool(
        name="cmw_wlan_fetch_all",
        description="Fetch all WLAN results (power, EVM, spectrum flatness, freq error)",
        inputSchema={
            "type": "object",
            "properties": _props({}),
        },
    ),
    _handle_wlan_fetch_all,
)

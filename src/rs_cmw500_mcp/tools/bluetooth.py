"""Bluetooth/BLE non-signaling measurement tools for CMW500."""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from ..models.cmw_types import BLEMode, BTMeasConfig, BTPacketType, BTTechnology
from .registry import registry
from .shared import _format_result, _get_cmw

logger = logging.getLogger(__name__)


# =============================================================================
# Handlers
# =============================================================================


async def _handle_bt_configure(args: dict[str, Any]) -> CallToolResult:
    """Configure Bluetooth measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    config = BTMeasConfig(
        technology=BTTechnology(args.get("technology", "LENergy")),
        ble_mode=BLEMode(args.get("ble_mode", "LE1M")),
        packet_type=BTPacketType(args.get("packet_type", "DH1")),
        frequency_hz=args.get("frequency_hz", 2.402e9),
        expected_power_dbm=args.get("expected_power_dbm", 10.0),
        meas_instance=args.get("meas_instance", 1),
    )
    await cmw.bt_configure(config)
    return _format_result({"status": "ok", "bt_config": config.to_dict()})


async def _handle_bt_set_technology(args: dict[str, Any]) -> CallToolResult:
    """Set Bluetooth technology."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    tech = args["technology"]
    n = args.get("meas_instance", 1)
    await cmw.bt_set_technology(tech, n)
    return _format_result({"status": "ok", "technology": tech})


async def _handle_bt_set_ble_mode(args: dict[str, Any]) -> CallToolResult:
    """Set BLE PHY mode."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    mode = args["ble_mode"]
    n = args.get("meas_instance", 1)
    await cmw.bt_set_ble_mode(mode, n)
    return _format_result({"status": "ok", "ble_mode": mode})


async def _handle_bt_set_packet_type(args: dict[str, Any]) -> CallToolResult:
    """Set Bluetooth Classic packet type."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    ptype = args["packet_type"]
    n = args.get("meas_instance", 1)
    await cmw.bt_set_packet_type(ptype, n)
    return _format_result({"status": "ok", "packet_type": ptype})


async def _handle_bt_set_frequency(args: dict[str, Any]) -> CallToolResult:
    """Set Bluetooth frequency."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    freq = args["frequency_hz"]
    n = args.get("meas_instance", 1)
    await cmw.bt_set_frequency(freq, n)
    return _format_result({"status": "ok", "frequency_hz": freq})


async def _handle_bt_set_expected_power(args: dict[str, Any]) -> CallToolResult:
    """Set Bluetooth expected power."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    power = args["power_dbm"]
    n = args.get("meas_instance", 1)
    await cmw.bt_set_expected_power(power, n)
    return _format_result({"status": "ok", "expected_power_dbm": power})


async def _handle_bt_trigger(args: dict[str, Any]) -> CallToolResult:
    """Trigger Bluetooth measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    n = args.get("meas_instance", 1)
    await cmw.bt_trigger(n)
    return _format_result({"status": "ok", "measurement": "bt_meval_triggered"})


async def _handle_bt_fetch_power(args: dict[str, Any]) -> CallToolResult:
    """Fetch Bluetooth power."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    n = args.get("meas_instance", 1)
    result = await cmw.bt_fetch_power(n)
    return _format_result(result)


async def _handle_bt_fetch_modulation(args: dict[str, Any]) -> CallToolResult:
    """Fetch Bluetooth modulation (DEVM)."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    n = args.get("meas_instance", 1)
    result = await cmw.bt_fetch_modulation(n)
    return _format_result(result)


async def _handle_bt_fetch_frequency(args: dict[str, Any]) -> CallToolResult:
    """Fetch Bluetooth frequency."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    n = args.get("meas_instance", 1)
    result = await cmw.bt_fetch_frequency(n)
    return _format_result(result)


async def _handle_bt_fetch_all(args: dict[str, Any]) -> CallToolResult:
    """Fetch all Bluetooth measurements."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    n = args.get("meas_instance", 1)
    result = await cmw.bt_fetch_all(n)
    return _format_result(result)


# =============================================================================
# Common schema helpers
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


def _props(*extra_dicts: dict) -> dict:
    """Merge property dicts."""
    merged: dict = {}
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
        name="cmw_bt_configure",
        description="Configure Bluetooth/BLE non-signaling measurement",
        inputSchema={
            "type": "object",
            "properties": _props(
                {
                    "technology": {
                        "type": "string",
                        "description": "Bluetooth technology",
                        "enum": ["CLASsic", "LENergy"],
                        "default": "LENergy",
                    },
                    "ble_mode": {
                        "type": "string",
                        "description": "BLE PHY mode (for LE only)",
                        "enum": ["LE1M", "LE2M", "LECS2", "LECS8"],
                        "default": "LE1M",
                    },
                    "packet_type": {
                        "type": "string",
                        "description": "BT Classic packet type",
                        "enum": [
                            "DH1",
                            "DH3",
                            "DH5",
                            "DM1",
                            "DM3",
                            "DM5",
                            "2DH1",
                            "2DH3",
                            "2DH5",
                            "3DH1",
                            "3DH3",
                            "3DH5",
                        ],
                        "default": "DH1",
                    },
                    "frequency_hz": {
                        "type": "number",
                        "description": "Frequency in Hz (default: 2.402 GHz)",
                        "default": 2.402e9,
                    },
                    "expected_power_dbm": {
                        "type": "number",
                        "description": "Expected power in dBm (default: 10)",
                        "default": 10.0,
                    },
                }
            ),
        },
    ),
    _handle_bt_configure,
)

registry.register(
    Tool(
        name="cmw_bt_set_technology",
        description="Set Bluetooth technology (Classic or Low Energy)",
        inputSchema={
            "type": "object",
            "properties": _props(
                {
                    "technology": {
                        "type": "string",
                        "description": "Bluetooth technology",
                        "enum": ["CLASsic", "LENergy"],
                    },
                }
            ),
            "required": ["technology"],
        },
    ),
    _handle_bt_set_technology,
)

registry.register(
    Tool(
        name="cmw_bt_set_ble_mode",
        description="Set BLE PHY mode (1M, 2M, Coded S2/S8)",
        inputSchema={
            "type": "object",
            "properties": _props(
                {
                    "ble_mode": {
                        "type": "string",
                        "description": "BLE PHY mode",
                        "enum": ["LE1M", "LE2M", "LECS2", "LECS8"],
                    },
                }
            ),
            "required": ["ble_mode"],
        },
    ),
    _handle_bt_set_ble_mode,
)

registry.register(
    Tool(
        name="cmw_bt_set_packet_type",
        description="Set Bluetooth Classic packet type (DH1/DH3/DH5/etc.)",
        inputSchema={
            "type": "object",
            "properties": _props(
                {
                    "packet_type": {
                        "type": "string",
                        "description": "Packet type",
                        "enum": [
                            "DH1",
                            "DH3",
                            "DH5",
                            "DM1",
                            "DM3",
                            "DM5",
                            "2DH1",
                            "2DH3",
                            "2DH5",
                            "3DH1",
                            "3DH3",
                            "3DH5",
                        ],
                    },
                }
            ),
            "required": ["packet_type"],
        },
    ),
    _handle_bt_set_packet_type,
)

registry.register(
    Tool(
        name="cmw_bt_set_frequency",
        description="Set Bluetooth measurement frequency in Hz",
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
    _handle_bt_set_frequency,
)

registry.register(
    Tool(
        name="cmw_bt_set_expected_power",
        description="Set Bluetooth expected input power in dBm",
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
    _handle_bt_set_expected_power,
)

registry.register(
    Tool(
        name="cmw_bt_trigger",
        description="Trigger Bluetooth multi-evaluation measurement",
        inputSchema={
            "type": "object",
            "properties": _props({}),
        },
    ),
    _handle_bt_trigger,
)

registry.register(
    Tool(
        name="cmw_bt_fetch_power",
        description="Fetch Bluetooth TX power measurement results",
        inputSchema={
            "type": "object",
            "properties": _props({}),
        },
    ),
    _handle_bt_fetch_power,
)

registry.register(
    Tool(
        name="cmw_bt_fetch_modulation",
        description="Fetch Bluetooth modulation (DEVM) measurement results",
        inputSchema={
            "type": "object",
            "properties": _props({}),
        },
    ),
    _handle_bt_fetch_modulation,
)

registry.register(
    Tool(
        name="cmw_bt_fetch_frequency",
        description="Fetch Bluetooth frequency measurement results",
        inputSchema={
            "type": "object",
            "properties": _props({}),
        },
    ),
    _handle_bt_fetch_frequency,
)

registry.register(
    Tool(
        name="cmw_bt_fetch_all",
        description="Fetch all Bluetooth measurement results (power, modulation, frequency)",
        inputSchema={
            "type": "object",
            "properties": _props({}),
        },
    ),
    _handle_bt_fetch_all,
)

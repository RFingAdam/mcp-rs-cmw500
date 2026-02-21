"""LTE signaling and measurement tools for CMW500."""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from ..models.cmw_types import CellConfig
from ..safety.validators import sanitize_scpi_param
from .registry import registry
from .shared import _format_result, _get_cmw

logger = logging.getLogger(__name__)


# =============================================================================
# LTE Signaling Handlers
# =============================================================================


async def _handle_lte_configure_cell(args: dict[str, Any]) -> CallToolResult:
    """Configure LTE cell."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    config = CellConfig(
        band=args["band"],
        bandwidth_mhz=args["bandwidth_mhz"],
        dl_earfcn=args["dl_earfcn"],
        dl_level_dbm=args.get("dl_level_dbm", -60.0),
    )
    await cmw.lte_configure_cell(config)
    return _format_result({"status": "ok", "cell_config": config.to_dict()})


async def _handle_lte_cell_on(args: dict[str, Any]) -> CallToolResult:
    """Turn on LTE cell."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.lte_cell_on()
    return _format_result({"status": "ok", "cell": "ON"})


async def _handle_lte_cell_off(args: dict[str, Any]) -> CallToolResult:
    """Turn off LTE cell."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.lte_cell_off()
    return _format_result({"status": "ok", "cell": "OFF"})


async def _handle_lte_get_connection_state(args: dict[str, Any]) -> CallToolResult:
    """Get LTE connection state."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    state = await cmw.lte_get_connection_state()
    return _format_result({"connection_state": state.strip()})


async def _handle_lte_configure_nas(args: dict[str, Any]) -> CallToolResult:
    """Configure NAS."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    mcc = sanitize_scpi_param(args.get("mcc", "001"))
    mnc = sanitize_scpi_param(args.get("mnc", "01"))
    await cmw.lte_configure_nas(mcc, mnc)
    return _format_result({"status": "ok", "mcc": mcc, "mnc": mnc})


async def _handle_lte_configure_bearer(args: dict[str, Any]) -> CallToolResult:
    """Configure bearer."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    apn = args.get("apn", "default")
    ip_version = args.get("ip_version", "IPV4")
    await cmw.lte_configure_bearer(apn=apn, ip_version=ip_version)
    return _format_result({"status": "ok", "apn": apn, "ip_version": ip_version})


async def _handle_lte_configure_cdrx(args: dict[str, Any]) -> CallToolResult:
    """Configure C-DRX."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    enabled = args.get("enabled", False)
    await cmw.lte_configure_cdrx(enabled)
    return _format_result({"status": "ok", "cdrx": "enabled" if enabled else "disabled"})


async def _handle_lte_get_ue_info(args: dict[str, Any]) -> CallToolResult:
    """Get UE info."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    info = await cmw.lte_get_ue_info()
    return _format_result(info)


# =============================================================================
# LTE Measurement Handlers
# =============================================================================


async def _handle_lte_meas_configure(args: dict[str, Any]) -> CallToolResult:
    """Configure LTE measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    stat_count = args.get("stat_count", 10)
    repetition = args.get("repetition", "SINGleshot")
    result = await cmw.lte_meas_configure(stat_count=stat_count, repetition=repetition)
    return _format_result(result)


async def _handle_lte_meas_trigger(args: dict[str, Any]) -> CallToolResult:
    """Trigger LTE measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.lte_meas_trigger()
    return _format_result({"status": "ok", "measurement": "lte_meval_triggered"})


async def _handle_lte_meas_fetch_power(args: dict[str, Any]) -> CallToolResult:
    """Fetch LTE power."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_power()
    return _format_result(result.to_dict())


async def _handle_lte_meas_fetch_evm(args: dict[str, Any]) -> CallToolResult:
    """Fetch LTE EVM."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_evm()
    return _format_result(result.to_dict())


async def _handle_lte_meas_fetch_aclr(args: dict[str, Any]) -> CallToolResult:
    """Fetch LTE ACLR."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_aclr()
    return _format_result(result.to_dict())


async def _handle_lte_meas_fetch_sem(args: dict[str, Any]) -> CallToolResult:
    """Fetch LTE SEM."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_sem()
    return _format_result(result.to_dict())


async def _handle_lte_meas_fetch_frequency_error(
    args: dict[str, Any],
) -> CallToolResult:
    """Fetch LTE frequency error."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_frequency_error()
    return _format_result(result)


async def _handle_lte_meas_fetch_all(args: dict[str, Any]) -> CallToolResult:
    """Fetch all LTE measurements."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_all()
    return _format_result(result)


# =============================================================================
# Registration
# =============================================================================

# LTE Signaling tools
registry.register(
    Tool(
        name="cmw_lte_configure_cell",
        description="Configure LTE cell parameters (band, BW, EARFCN, DL level)",
        inputSchema={
            "type": "object",
            "properties": {
                "band": {
                    "type": "integer",
                    "description": "LTE band number (e.g., 1, 3, 7, 41)",
                },
                "bandwidth_mhz": {
                    "type": "number",
                    "description": "Channel bandwidth in MHz (1.4, 3, 5, 10, 15, 20)",
                    "enum": [1.4, 3, 5, 10, 15, 20],
                },
                "dl_earfcn": {
                    "type": "integer",
                    "description": "Downlink EARFCN channel number",
                },
                "dl_level_dbm": {
                    "type": "number",
                    "description": "Downlink signal level in dBm (default: -60)",
                    "default": -60,
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
            "required": ["band", "bandwidth_mhz", "dl_earfcn"],
        },
    ),
    _handle_lte_configure_cell,
)

registry.register(
    Tool(
        name="cmw_lte_cell_on",
        description="Turn on LTE cell (start base station emulation)",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_cell_on,
)

registry.register(
    Tool(
        name="cmw_lte_cell_off",
        description="Turn off LTE cell",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_cell_off,
)

registry.register(
    Tool(
        name="cmw_lte_get_connection_state",
        description="Get LTE UE connection state (ATT, CONN, IDLE, etc.)",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_get_connection_state,
)

registry.register(
    Tool(
        name="cmw_lte_configure_nas",
        description="Configure LTE NAS parameters (MCC, MNC)",
        inputSchema={
            "type": "object",
            "properties": {
                "mcc": {
                    "type": "string",
                    "description": "Mobile Country Code (default: 001)",
                    "default": "001",
                },
                "mnc": {
                    "type": "string",
                    "description": "Mobile Network Code (default: 01)",
                    "default": "01",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_configure_nas,
)

registry.register(
    Tool(
        name="cmw_lte_configure_bearer",
        description="Configure default EPS bearer (APN and IP version)",
        inputSchema={
            "type": "object",
            "properties": {
                "apn": {
                    "type": "string",
                    "description": "Access Point Name (default: 'default')",
                    "default": "default",
                },
                "ip_version": {
                    "type": "string",
                    "description": "IP version",
                    "enum": ["IPV4", "IPV6", "IPV4V6"],
                    "default": "IPV4",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_configure_bearer,
)

registry.register(
    Tool(
        name="cmw_lte_configure_cdrx",
        description="Configure Connected DRX (C-DRX) enable/disable",
        inputSchema={
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "description": "Enable C-DRX (default: false)",
                    "default": False,
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_configure_cdrx,
)

registry.register(
    Tool(
        name="cmw_lte_get_ue_info",
        description="Get UE (User Equipment) information including connection state",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_get_ue_info,
)

# LTE Measurement tools
registry.register(
    Tool(
        name="cmw_lte_meas_configure",
        description="Configure LTE multi-evaluation measurement (subframe count, repetition)",
        inputSchema={
            "type": "object",
            "properties": {
                "stat_count": {
                    "type": "integer",
                    "description": "Number of subframes to measure (default: 10)",
                    "default": 10,
                },
                "repetition": {
                    "type": "string",
                    "description": "Measurement repetition mode",
                    "enum": ["SINGleshot", "CONTinuous"],
                    "default": "SINGleshot",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_meas_configure,
)

registry.register(
    Tool(
        name="cmw_lte_meas_trigger",
        description="Trigger LTE multi-evaluation measurement",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_meas_trigger,
)

registry.register(
    Tool(
        name="cmw_lte_meas_fetch_power",
        description="Fetch LTE TX power measurement results",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_meas_fetch_power,
)

registry.register(
    Tool(
        name="cmw_lte_meas_fetch_evm",
        description="Fetch LTE EVM (Error Vector Magnitude) measurement results",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_meas_fetch_evm,
)

registry.register(
    Tool(
        name="cmw_lte_meas_fetch_aclr",
        description="Fetch LTE ACLR (Adjacent Channel Leakage Ratio) measurement results",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_meas_fetch_aclr,
)

registry.register(
    Tool(
        name="cmw_lte_meas_fetch_sem",
        description="Fetch LTE SEM (Spectrum Emission Mask) measurement results",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_meas_fetch_sem,
)

registry.register(
    Tool(
        name="cmw_lte_meas_fetch_frequency_error",
        description="Fetch LTE frequency error measurement results",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_meas_fetch_frequency_error,
)

registry.register(
    Tool(
        name="cmw_lte_meas_fetch_all",
        description="Fetch all LTE measurement results (power, EVM, ACLR, SEM)",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_lte_meas_fetch_all,
)

"""Advanced GPRF tools for CMW500."""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from .registry import registry
from .shared import _format_result, _get_cmw

logger = logging.getLogger(__name__)


# =============================================================================
# Handlers
# =============================================================================


async def _handle_meas_set_trigger(args: dict[str, Any]) -> CallToolResult:
    """Set measurement trigger source and threshold."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    source = args.get("source", "IF Power")
    await cmw.meas_set_trigger_source(source)
    threshold = args.get("threshold_dbm")
    if threshold is not None:
        await cmw.meas_set_trigger_threshold(threshold)
    return _format_result(
        {
            "status": "ok",
            "trigger_source": source,
            "threshold_dbm": threshold,
        }
    )


async def _handle_meas_set_power_filter(args: dict[str, Any]) -> CallToolResult:
    """Set power measurement filter."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    filter_type = args.get("filter_type", "NONE")
    bandwidth = args.get("bandwidth_hz")
    await cmw.meas_set_power_filter(filter_type, bandwidth)
    return _format_result(
        {
            "status": "ok",
            "filter_type": filter_type,
            "bandwidth_hz": bandwidth,
        }
    )


async def _handle_gen_set_baseband_mode(args: dict[str, Any]) -> CallToolResult:
    """Set generator baseband mode."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    mode = args.get("mode", "CW")
    await cmw.gen_set_baseband_mode(mode)
    return _format_result({"status": "ok", "baseband_mode": mode})


async def _handle_set_port(args: dict[str, Any]) -> CallToolResult:
    """Set generator and/or analyzer port."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    gen_port = args.get("generator_port")
    meas_port = args.get("analyzer_port")
    if gen_port:
        await cmw.gen_set_port(gen_port)
    if meas_port:
        await cmw.meas_set_port(meas_port)
    return _format_result(
        {
            "status": "ok",
            "generator_port": gen_port,
            "analyzer_port": meas_port,
        }
    )


async def _handle_meas_set_user_margin(args: dict[str, Any]) -> CallToolResult:
    """Set analyzer user margin."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    margin = args["margin_db"]
    await cmw.meas_set_user_margin(margin)
    return _format_result({"status": "ok", "user_margin_db": margin})


async def _handle_system_all_off(args: dict[str, Any]) -> CallToolResult:
    """Turn off all generators and measurements."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.system_all_off()
    return _format_result({"status": "ok", "action": "all_off"})


# =============================================================================
# Registration
# =============================================================================

registry.register(
    Tool(
        name="cmw_meas_set_trigger",
        description="Set GPRF measurement trigger source and threshold",
        inputSchema={
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Trigger source (default: 'IF Power')",
                    "default": "IF Power",
                },
                "threshold_dbm": {
                    "type": "number",
                    "description": "Trigger threshold in dBm (optional)",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_meas_set_trigger,
)

registry.register(
    Tool(
        name="cmw_meas_set_power_filter",
        description="Set GPRF power measurement filter type and bandwidth",
        inputSchema={
            "type": "object",
            "properties": {
                "filter_type": {
                    "type": "string",
                    "description": "Filter type (NONE, GAUSs, etc.)",
                    "default": "NONE",
                },
                "bandwidth_hz": {
                    "type": "number",
                    "description": "Filter bandwidth in Hz (optional)",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_meas_set_power_filter,
)

registry.register(
    Tool(
        name="cmw_gen_set_baseband_mode",
        description="Set GPRF generator baseband mode (CW, ARB, etc.)",
        inputSchema={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "description": "Baseband mode",
                    "enum": ["CW", "ARB"],
                    "default": "CW",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_gen_set_baseband_mode,
)

registry.register(
    Tool(
        name="cmw_set_port",
        description="Set GPRF generator/analyzer RF port connector",
        inputSchema={
            "type": "object",
            "properties": {
                "generator_port": {
                    "type": "string",
                    "description": "Generator output port/connector",
                },
                "analyzer_port": {
                    "type": "string",
                    "description": "Analyzer input port/connector",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_set_port,
)

registry.register(
    Tool(
        name="cmw_meas_set_user_margin",
        description="Set GPRF analyzer user margin in dB",
        inputSchema={
            "type": "object",
            "properties": {
                "margin_db": {
                    "type": "number",
                    "description": "User margin in dB",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
            "required": ["margin_db"],
        },
    ),
    _handle_meas_set_user_margin,
)

registry.register(
    Tool(
        name="cmw_system_all_off",
        description="Turn off all generators and measurements (safe state)",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_system_all_off,
)

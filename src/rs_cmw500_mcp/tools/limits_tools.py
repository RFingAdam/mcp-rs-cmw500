"""Limit management tools for CMW500."""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from ..limits import LimitLine, LimitSegment
from .registry import registry
from .shared import _format_result, _limit_manager, _measurement_lock

logger = logging.getLogger(__name__)


# =============================================================================
# Handlers
# =============================================================================


async def _handle_define_limit(args: dict[str, Any]) -> CallToolResult:
    """Define a limit."""
    name = args["name"]
    parameter = args["parameter"]
    max_value = args.get("max_value")
    min_value = args.get("min_value")
    unit = args.get("unit", "")

    segment = LimitSegment(
        parameter=parameter,
        max_value=max_value,
        min_value=min_value,
        unit=unit,
        name=name,
    )
    limit = LimitLine(name=name, segments=[segment])
    async with _measurement_lock:
        _limit_manager.add_limit(limit)

    return _format_result(
        {
            "status": "ok",
            "limit_defined": name,
            "parameter": parameter,
            "max_value": max_value,
            "min_value": min_value,
        }
    )


async def _handle_check_limits(args: dict[str, Any]) -> CallToolResult:
    """Check measurements against limits."""
    measurements = args["measurements"]
    # Convert to float dict
    float_measurements = {k: float(v) for k, v in measurements.items()}
    async with _measurement_lock:
        result = _limit_manager.get_overall_status(float_measurements)
    return _format_result(result)


async def _handle_clear_limits(args: dict[str, Any]) -> CallToolResult:
    """Clear all limits."""
    async with _measurement_lock:
        _limit_manager.clear_limits()
    return _format_result({"status": "ok", "action": "limits_cleared"})


async def _handle_list_limits(args: dict[str, Any]) -> CallToolResult:
    """List all limits."""
    async with _measurement_lock:
        limit_names = _limit_manager.list_limits()
        limits_detail = []
        for name in limit_names:
            limit = _limit_manager.get_limit(name)
            if limit:
                limits_detail.append(limit.to_dict())
    return _format_result({"limits": limits_detail, "count": len(limits_detail)})


# =============================================================================
# Registration
# =============================================================================

registry.register(
    Tool(
        name="cmw_define_limit",
        description="Define a pass/fail limit for measurement checking",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Limit name",
                },
                "parameter": {
                    "type": "string",
                    "description": "Parameter name to check (e.g., power_dbm, evm_percent)",
                },
                "max_value": {
                    "type": "number",
                    "description": "Maximum allowed value",
                },
                "min_value": {
                    "type": "number",
                    "description": "Minimum allowed value",
                },
                "unit": {
                    "type": "string",
                    "description": "Unit of measurement (e.g., dBm, %)",
                    "default": "",
                },
            },
            "required": ["name", "parameter"],
        },
    ),
    _handle_define_limit,
)

registry.register(
    Tool(
        name="cmw_check_limits",
        description="Check measurement values against defined limits",
        inputSchema={
            "type": "object",
            "properties": {
                "measurements": {
                    "type": "object",
                    "description": "Dictionary of parameter:value pairs to check",
                },
            },
            "required": ["measurements"],
        },
    ),
    _handle_check_limits,
)

registry.register(
    Tool(
        name="cmw_clear_limits",
        description="Clear all defined limits",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    _handle_clear_limits,
)

registry.register(
    Tool(
        name="cmw_list_limits",
        description="List all defined limits",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    _handle_list_limits,
)

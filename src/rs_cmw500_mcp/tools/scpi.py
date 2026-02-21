"""Raw SCPI and system tools for CMW500."""

import asyncio
import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from ..config import get_settings
from ..exceptions import CMW500Error
from .registry import registry
from .shared import _format_error, _format_result, _get_cmw

logger = logging.getLogger(__name__)


# =============================================================================
# Handlers
# =============================================================================


async def _handle_scpi_send(args: dict[str, Any]) -> CallToolResult:
    """Send raw SCPI command."""
    settings = get_settings()
    if not settings.allow_raw_scpi:
        return _format_error(
            ValueError("Raw SCPI access is disabled. Set CMW_ALLOW_RAW_SCPI=true to enable.")
        )

    cmw = await _get_cmw(args.get("host"), args.get("port"))
    command = args["command"]
    logger.warning(f"Raw SCPI send: {command!r}")
    await cmw.scpi_send(command)
    return _format_result({"status": "ok", "command": command})


async def _handle_scpi_query(args: dict[str, Any]) -> CallToolResult:
    """Send raw SCPI query."""
    settings = get_settings()
    if not settings.allow_raw_scpi:
        return _format_error(
            ValueError("Raw SCPI access is disabled. Set CMW_ALLOW_RAW_SCPI=true to enable.")
        )

    cmw = await _get_cmw(args.get("host"), args.get("port"))
    command = args["command"]
    logger.warning(f"Raw SCPI query: {command!r}")
    response = await cmw.scpi_query(command)
    return _format_result({"command": command, "response": response})


async def _handle_reset(args: dict[str, Any]) -> CallToolResult:
    """Reset CMW500.

    Uses configurable timeout (preset_timeout) to prevent hanging indefinitely.
    """
    settings = get_settings()
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    try:
        await asyncio.wait_for(cmw.reset(), timeout=settings.preset_timeout)
    except asyncio.TimeoutError:
        raise CMW500Error(
            f"Reset operation timed out after {settings.preset_timeout}s. "
            "The CMW500 may be unresponsive. Configure CMW_PRESET_TIMEOUT "
            "to increase the timeout."
        )
    return _format_result({"status": "ok", "action": "reset"})


async def _handle_preset(args: dict[str, Any]) -> CallToolResult:
    """Preset CMW500.

    Uses configurable timeout (preset_timeout) to prevent hanging indefinitely.
    """
    settings = get_settings()
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    try:
        await asyncio.wait_for(cmw.preset(), timeout=settings.preset_timeout)
    except asyncio.TimeoutError:
        raise CMW500Error(
            f"Preset operation timed out after {settings.preset_timeout}s. "
            "The CMW500 may be unresponsive. Configure CMW_PRESET_TIMEOUT "
            "to increase the timeout."
        )
    return _format_result({"status": "ok", "action": "preset"})


# =============================================================================
# Registration
# =============================================================================

registry.register(
    Tool(
        name="cmw_scpi_send",
        description="Send raw SCPI command to CMW500 (no response)",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "SCPI command string",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
            "required": ["command"],
        },
    ),
    _handle_scpi_send,
)

registry.register(
    Tool(
        name="cmw_scpi_query",
        description="Send SCPI query and return response",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "SCPI query (should end with ?)",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
            "required": ["command"],
        },
    ),
    _handle_scpi_query,
)

registry.register(
    Tool(
        name="cmw_reset",
        description="Reset CMW500 to default state (*RST)",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_reset,
)

registry.register(
    Tool(
        name="cmw_preset",
        description="Full system preset of CMW500",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_preset,
)

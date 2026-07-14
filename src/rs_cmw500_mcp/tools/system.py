"""System / SCPI-hygiene tools: error queue and OPC-synchronised raw commands.

These make the "reach anything" raw-SCPI path fail loudly: drain the SCPI error
queue and run a command with an explicit operation-complete sync.
"""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from ..config import get_settings
from .registry import registry
from .shared import _format_error, _format_result, _get_cmw

logger = logging.getLogger(__name__)

_HOST_PORT = {"host": {"type": "string"}, "port": {"type": "integer"}}


async def _handle_system_error(args: dict[str, Any]) -> CallToolResult:
    """Drain the SCPI error queue (SYSTem:ERRor?) and report any errors."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    errors = await cmw.get_errors()
    return _format_result({"error_count": len(errors), "errors": errors, "clean": not errors})


async def _handle_scpi_query_opc(args: dict[str, Any]) -> CallToolResult:
    """Send a raw SCPI command and wait for *OPC? before returning."""
    settings = get_settings()
    if not settings.allow_raw_scpi:
        return _format_error(
            ValueError("Raw SCPI access is disabled. Set CMW_ALLOW_RAW_SCPI=true to enable.")
        )
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    command = args["command"]
    logger.warning(f"Raw SCPI send+OPC: {command!r}")
    completed = await cmw.scpi_send_opc(command)
    result: dict[str, Any] = {"status": "ok", "command": command, "opc": completed}
    if settings.auto_error_check:
        result["errors"] = await cmw.get_errors()
    return _format_result(result)


registry.register(
    Tool(
        name="cmw_system_error",
        description=(
            "Drain and return the CMW500 SCPI error queue (SYSTem:ERRor?). Use after "
            "raw SCPI or when a command may have been rejected. clean=true means no errors."
        ),
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_system_error,
)

registry.register(
    Tool(
        name="cmw_scpi_query_opc",
        description=(
            "Send a raw SCPI command and block on *OPC? until the instrument reports "
            "completion. Gated by allow_raw_scpi. Use for slow state changes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "SCPI command to send"},
                **_HOST_PORT,
            },
            "required": ["command"],
        },
    ),
    _handle_scpi_query_opc,
)

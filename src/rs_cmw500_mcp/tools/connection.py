"""Connection management tools for CMW500."""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from ..config import get_settings
from ..driver import CMW500Driver
from ..exceptions import CMW500Error
from .registry import registry
from .shared import _close_cmw, _format_result, _get_cmw

logger = logging.getLogger(__name__)


# =============================================================================
# Handlers
# =============================================================================


async def _handle_discover(args: dict[str, Any]) -> CallToolResult:
    """Scan for CMW500 instruments."""
    host = args.get("host", "127.0.0.1")
    start_port = args.get("start_port", 5025)
    end_port = args.get("end_port", 5030)

    found = []
    for port in range(start_port, end_port + 1):
        try:
            cmw = CMW500Driver(host=host, port=port, timeout=2.0)
            await cmw.connect()
            info = await cmw.identify()
            found.append(
                {
                    "host": host,
                    "port": port,
                    "model": info.model,
                    "serial": info.serial_number,
                    "firmware": info.firmware_version,
                }
            )
            await cmw.disconnect()
        except (OSError, CMW500Error) as e:
            logger.debug(f"No instrument at {host}:{port}: {e}")
            continue

    return _format_result(
        {
            "scan_range": f"{host}:{start_port}-{end_port}",
            "instruments_found": len(found),
            "instruments": found,
        }
    )


async def _handle_connect(args: dict[str, Any]) -> CallToolResult:
    """Connect to CMW500."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    info = await cmw.identify()
    return _format_result(
        {
            "status": "connected",
            "address": cmw._scpi.address,
            "instrument": info.to_dict(),
        }
    )


async def _handle_disconnect(args: dict[str, Any]) -> CallToolResult:
    """Disconnect from CMW500."""
    settings = get_settings()
    host = args.get("host", settings.default_host)
    port = args.get("port", settings.default_port)
    closed = await _close_cmw(host, port)
    return _format_result(
        {
            "status": "disconnected" if closed else "not_connected",
            "address": f"{host}:{port}",
        }
    )


async def _handle_identify(args: dict[str, Any]) -> CallToolResult:
    """Get CMW500 identification."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    info = await cmw.identify()
    return _format_result(info.to_dict())


async def _handle_get_status(args: dict[str, Any]) -> CallToolResult:
    """Get CMW500 status."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    status = await cmw.get_status()
    return _format_result(status)


async def _handle_query_options(args: dict[str, Any]) -> CallToolResult:
    """Query installed options."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    options = await cmw.query_options()
    return _format_result({"options": options, "count": len(options)})


# =============================================================================
# Registration
# =============================================================================

registry.register(
    Tool(
        name="cmw_discover",
        description="Scan for CMW500 instruments on the network (port 5025)",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Host to scan (default: 127.0.0.1)",
                    "default": "127.0.0.1",
                },
                "start_port": {
                    "type": "integer",
                    "description": "Start port (default: 5025)",
                    "default": 5025,
                },
                "end_port": {
                    "type": "integer",
                    "description": "End port (default: 5030)",
                    "default": 5030,
                },
            },
        },
    ),
    _handle_discover,
)

registry.register(
    Tool(
        name="cmw_connect",
        description="Connect to CMW500 at specified host:port",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "CMW500 hostname or IP (default: from config)",
                },
                "port": {
                    "type": "integer",
                    "description": "TCP port (default: 5025)",
                },
            },
        },
    ),
    _handle_connect,
)

registry.register(
    Tool(
        name="cmw_disconnect",
        description="Disconnect from CMW500",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_disconnect,
)

registry.register(
    Tool(
        name="cmw_identify",
        description="Get CMW500 identification (*IDN?): manufacturer, model, serial, firmware",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_identify,
)

registry.register(
    Tool(
        name="cmw_get_status",
        description="Get CMW500 connection and configuration status",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_get_status,
)

registry.register(
    Tool(
        name="cmw_query_options",
        description="Query installed hardware and software options",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_query_options,
)

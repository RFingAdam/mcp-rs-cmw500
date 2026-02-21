"""Shared state and utilities for tool modules."""

import asyncio
import json
import logging
from typing import Any

from mcp.types import CallToolResult, TextContent

from ..config import get_settings
from ..driver import CMW500Driver
from ..limits import LimitManager
from ..state import StateManager
from ..templates import (
    BLERxTemplate,
    BLETxTemplate,
    BTClassicTxTemplate,
    GPRFPowerTemplate,
    LTETxPowerTemplate,
    MeasurementTemplate,
    NonSignalingRxTemplate,
    WLANRxTemplate,
    WLANTxTemplate,
)

logger = logging.getLogger(__name__)

# Global CMW500 connection manager
_cmw_connections: dict[str, CMW500Driver] = {}

# Global template storage
_current_template: MeasurementTemplate | None = None

# Global limit manager
_limit_manager = LimitManager()

# Global state manager
_state_manager = StateManager()

# Template registry
_template_registry: dict[str, type] = {
    "lte_tx_power": LTETxPowerTemplate,
    "gprf_power": GPRFPowerTemplate,
    "nonsig_rx": NonSignalingRxTemplate,
    "wlan_tx": WLANTxTemplate,
    "wlan_rx": WLANRxTemplate,
    "ble_tx": BLETxTemplate,
    "ble_rx": BLERxTemplate,
    "bt_classic_tx": BTClassicTxTemplate,
}

# Asyncio locks for shared mutable state (Issue #4)
# Lock ordering: _connection_lock -> _template_lock -> _measurement_lock
_connection_lock = asyncio.Lock()
_template_lock = asyncio.Lock()
_measurement_lock = asyncio.Lock()


def _get_connection_key(host: str, port: int) -> str:
    """Generate unique key for connection."""
    return f"{host}:{port}"


async def _get_cmw(host: str | None = None, port: int | None = None) -> CMW500Driver:
    """Get or create CMW500 connection.

    Thread-safe via _connection_lock to prevent race conditions
    when multiple MCP tool calls access the connection pool concurrently.
    """
    settings = get_settings()
    host = host or settings.default_host
    port = port or settings.default_port
    key = _get_connection_key(host, port)

    async with _connection_lock:
        if key in _cmw_connections:
            cmw = _cmw_connections[key]
            if cmw.is_connected:
                return cmw
            # Clean up stale connection
            try:
                await cmw.disconnect()
            except OSError as e:
                logger.warning(f"Error cleaning up stale connection {key}: {e}")

        # Create new connection
        cmw = CMW500Driver(
            host=host,
            port=port,
            timeout=settings.connection_timeout,
            command_timeout=settings.command_timeout,
            safety_limits=settings.get_safety_limits(),
        )
        await cmw.connect()
        _cmw_connections[key] = cmw
        return cmw


async def _close_cmw(host: str, port: int) -> bool:
    """Close CMW500 connection.

    Thread-safe via _connection_lock.
    """
    key = _get_connection_key(host, port)
    async with _connection_lock:
        if key in _cmw_connections:
            cmw = _cmw_connections.pop(key)
            await cmw.disconnect()
            return True
        return False


def _format_result(result: Any) -> CallToolResult:
    """Format result as MCP CallToolResult (success)."""
    if isinstance(result, (dict, list)):
        text = json.dumps(result, indent=2, default=str)
    else:
        text = str(result)
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        isError=False,
    )


def _format_error(error: Exception) -> CallToolResult:
    """Format error as MCP CallToolResult with isError=True.

    This ensures the MCP protocol correctly signals error responses
    to the client, allowing proper error handling downstream.
    """
    return CallToolResult(
        content=[TextContent(type="text", text=f"Error: {error}")],
        isError=True,
    )

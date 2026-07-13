"""MCP tool definitions and handlers for CMW500 operations.

This package provides a registry-based tool system. Each technology module
registers its tools at import time. The public API (get_tools, handle_tool)
remains backward-compatible with server.py.
"""

import logging
from typing import Any

from mcp.types import CallToolResult, TextContent, Tool

from ..exceptions import CMW500Error
from .registry import registry

logger = logging.getLogger(__name__)

# Import all tool modules to trigger registration.
# Order doesn't matter since each module registers independently.
from . import (  # noqa: F401, E402
    bluetooth,
    bluetooth_signaling,
    coex,
    connection,
    gprf,
    gprf_advanced,
    limits_tools,
    lte,
    lte_rx,
    profile_tools,
    rf_planner,
    scpi,
    state_tools,
    system,
    templates_tools,
    wlan,
    wlan_signaling,
)


def get_tools() -> list[Tool]:
    """Get all MCP tool definitions.

    Returns the same list format as the original tools.py for
    backward compatibility with server.py.
    """
    return registry.get_all_tools()


async def handle_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Handle tool invocation with centralized error handling.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        CallToolResult with content and isError flag
    """
    try:
        return await registry.dispatch(name, arguments)
    except CMW500Error as e:
        logger.error(f"CMW500 error in {name}: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            isError=True,
        )
    except (ConnectionError, TimeoutError, OSError) as e:
        logger.error(f"Connection/IO error in {name}: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            isError=True,
        )
    except ValueError as e:
        logger.error(f"Validation error in {name}: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            isError=True,
        )
    except KeyError as e:
        logger.error(f"Missing argument in {name}: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: Missing required argument: {e}")],
            isError=True,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in {name}: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            isError=True,
        )

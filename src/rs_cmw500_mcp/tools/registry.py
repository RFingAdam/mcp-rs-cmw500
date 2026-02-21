"""Tool registry for MCP tool definitions and dispatch."""

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from mcp.types import CallToolResult, TextContent, Tool

logger = logging.getLogger(__name__)

ToolHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, CallToolResult]]


class ToolRegistry:
    """Registry for MCP tools with dispatch support.

    Tools are registered at import time by each tool module.
    The registry provides tool listing and name-based dispatch.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, tool: Tool, handler: ToolHandler) -> None:
        """Register a tool definition with its handler.

        Args:
            tool: MCP Tool definition
            handler: Async handler function for the tool

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler

    def get_all_tools(self) -> list[Tool]:
        """Return all registered tool definitions."""
        return list(self._tools.values())

    async def dispatch(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        """Dispatch a tool call by name.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            CallToolResult from the handler
        """
        handler = self._handlers.get(name)
        if handler is None:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Unknown tool: {name}")],
                isError=True,
            )
        return await handler(arguments)

    @property
    def tool_count(self) -> int:
        """Number of registered tools."""
        return len(self._tools)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools


# Singleton registry instance
registry = ToolRegistry()

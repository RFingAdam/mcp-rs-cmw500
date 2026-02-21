"""MCP server for Rohde & Schwarz CMW500 automation."""

import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, Tool

from .config import get_settings
from .tools import get_tools, handle_tool

logger = logging.getLogger(__name__)


def create_server() -> Server:
    """Create and configure MCP server."""
    server = Server("rs-cmw500-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return list of available tools."""
        return get_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        """Handle tool invocation.

        Returns CallToolResult directly so the MCP framework
        can propagate isError=True for error responses.
        """
        logger.debug(f"Tool called: {name} with args: {arguments}")
        return await handle_tool(name, arguments)

    return server


async def run_server() -> None:
    """Run the MCP server with stdio transport."""
    settings = get_settings()
    settings.configure_logging()

    logger.info("Starting R&S CMW500 MCP Server")
    logger.info(f"Default connection: {settings.default_host}:{settings.default_port}")

    server = create_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Main entry point."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()

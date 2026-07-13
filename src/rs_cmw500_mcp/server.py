"""MCP server for Rohde & Schwarz CMW500 automation."""

import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, GetPromptResult, Prompt, Resource, Tool

from . import prompts as prompts_mod
from . import resources as resources_mod
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

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """Return the curated SCPI reference + dynamic capability resources."""
        return resources_mod.list_resources()

    @server.read_resource()
    async def read_resource(uri: Any) -> list[ReadResourceContents]:
        """Read a cmw:// resource by URI."""
        content, mime = await resources_mod.read_resource(str(uri))
        return [ReadResourceContents(content=content, mime_type=mime)]

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        """Return the guided coexistence / RX workflow prompts."""
        return prompts_mod.list_prompts()

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
        """Render a guided prompt with the supplied arguments."""
        return prompts_mod.get_prompt(name, arguments)

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

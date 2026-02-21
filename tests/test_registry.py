"""Tests for the MCP tool registry."""

from unittest.mock import AsyncMock

import pytest
from mcp.types import CallToolResult, TextContent, Tool

from rs_cmw500_mcp.tools import get_tools
from rs_cmw500_mcp.tools.registry import ToolRegistry, registry


class TestRegistrySingleton:
    """Tests against the populated singleton registry."""

    def test_get_tools_returns_nonempty_list(self):
        """get_tools must return a non-empty list of registered tools."""
        tools = get_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_no_duplicate_tool_names(self):
        """Every registered tool name must be unique."""
        tools = get_tools()
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), (
            f"Duplicate tool names found: {[n for n in names if names.count(n) > 1]}"
        )

    def test_all_tools_have_nonempty_name_and_description(self):
        """Each tool must have a non-empty name and description."""
        for tool in get_tools():
            assert tool.name, f"Tool has empty/None name: {tool}"
            assert tool.description, f"Tool {tool.name!r} has empty/None description"

    def test_all_tools_have_valid_input_schema(self):
        """Each tool's inputSchema must be an object-typed JSON Schema."""
        for tool in get_tools():
            schema = tool.inputSchema
            assert schema is not None, f"Tool {tool.name!r} has no inputSchema"
            assert schema.get("type") == "object", (
                f"Tool {tool.name!r} inputSchema type is {schema.get('type')!r}, expected 'object'"
            )

    def test_get_tools_returns_tool_instances(self):
        """get_tools must return instances of mcp.types.Tool."""
        for tool in get_tools():
            assert isinstance(tool, Tool), f"Expected Tool instance, got {type(tool).__name__}"

    def test_tool_count_at_least_68(self):
        """The registry must contain at least 68 tools across all modules."""
        count = len(get_tools())
        assert count >= 68, f"Expected at least 68 tools, got {count}"

    def test_each_tool_has_a_handler(self):
        """Every registered tool must have a corresponding handler."""
        for tool in get_tools():
            assert registry.has_tool(tool.name), (
                f"Tool {tool.name!r} is in get_tools() but not in registry"
            )
            # The handler dict should contain the same key
            assert tool.name in registry._handlers, (
                f"Tool {tool.name!r} registered without a handler"
            )

    def test_well_known_tools_exist(self):
        """Specific well-known tools must be present in the registry."""
        expected = {
            "cmw_connect",
            "cmw_wlan_configure",
            "cmw_bt_configure",
        }
        names = {t.name for t in get_tools()}
        missing = expected - names
        assert not missing, f"Missing well-known tools: {missing}"

    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool_returns_is_error(self):
        """Dispatching an unregistered tool name must return isError=True."""
        result = await registry.dispatch("__no_such_tool__", {})
        assert isinstance(result, CallToolResult)
        assert result.isError is True
        assert any("Unknown tool" in c.text for c in result.content), (
            "Error message should mention 'Unknown tool'"
        )

    @pytest.mark.asyncio
    async def test_dispatch_calls_correct_handler(self):
        """Registry.dispatch must invoke the handler registered for the name."""
        # Build an isolated registry so we don't pollute the singleton.
        local = ToolRegistry()
        sentinel = CallToolResult(
            content=[TextContent(type="text", text="handler-called")],
            isError=False,
        )
        handler = AsyncMock(return_value=sentinel)
        tool = Tool(
            name="test_dispatch_target",
            description="unit-test tool",
            inputSchema={"type": "object", "properties": {}},
        )
        local.register(tool, handler)

        result = await local.dispatch("test_dispatch_target", {"key": "value"})

        handler.assert_awaited_once_with({"key": "value"})
        assert result is sentinel


class TestToolRegistryUnit:
    """Unit tests for ToolRegistry behaviour independent of loaded modules."""

    def test_register_raises_on_duplicate(self):
        """Registering a tool with the same name twice must raise ValueError."""
        local = ToolRegistry()
        tool = Tool(
            name="dup_tool",
            description="first",
            inputSchema={"type": "object"},
        )
        local.register(tool, AsyncMock())
        with pytest.raises(ValueError, match="already registered"):
            local.register(tool, AsyncMock())

    def test_tool_count_property(self):
        """The tool_count property must reflect the number of registered tools."""
        local = ToolRegistry()
        assert local.tool_count == 0
        for i in range(3):
            local.register(
                Tool(
                    name=f"tc_{i}",
                    description=f"tool {i}",
                    inputSchema={"type": "object"},
                ),
                AsyncMock(),
            )
        assert local.tool_count == 3

    def test_has_tool(self):
        """has_tool must return True only for registered names."""
        local = ToolRegistry()
        tool = Tool(
            name="probe",
            description="probe tool",
            inputSchema={"type": "object"},
        )
        assert not local.has_tool("probe")
        local.register(tool, AsyncMock())
        assert local.has_tool("probe")
        assert not local.has_tool("other")

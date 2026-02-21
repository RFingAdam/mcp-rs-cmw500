"""Tests for MCP tool definitions and handlers."""

import asyncio

import pytest
from mcp.types import CallToolResult

from rs_cmw500_mcp.tools import get_tools, handle_tool


class TestToolDefinitions:
    """Test that all tools are properly defined."""

    def test_get_tools_returns_list(self):
        tools = get_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_all_tools_have_names(self):
        tools = get_tools()
        for tool in tools:
            assert tool.name is not None
            assert len(tool.name) > 0

    def test_all_tools_have_descriptions(self):
        tools = get_tools()
        for tool in tools:
            assert tool.description is not None
            assert len(tool.description) > 0

    def test_all_tools_have_schemas(self):
        tools = get_tools()
        for tool in tools:
            assert tool.inputSchema is not None
            assert tool.inputSchema["type"] == "object"

    def test_tool_names_prefixed(self):
        """All tool names should start with cmw_."""
        tools = get_tools()
        for tool in tools:
            assert tool.name.startswith("cmw_"), f"Tool {tool.name} not prefixed with cmw_"

    def test_expected_tool_count(self):
        """Verify we have the expected number of tools."""
        tools = get_tools()
        # We should have ~50 tools
        assert len(tools) >= 45, f"Expected at least 45 tools, got {len(tools)}"

    def test_connection_tools_present(self):
        """Verify connection tools are present."""
        tools = get_tools()
        names = {t.name for t in tools}
        assert "cmw_discover" in names
        assert "cmw_connect" in names
        assert "cmw_disconnect" in names
        assert "cmw_identify" in names
        assert "cmw_get_status" in names
        assert "cmw_query_options" in names

    def test_generator_tools_present(self):
        """Verify generator tools are present."""
        tools = get_tools()
        names = {t.name for t in tools}
        assert "cmw_gen_set_frequency" in names
        assert "cmw_gen_set_level" in names
        assert "cmw_gen_output_on" in names
        assert "cmw_gen_output_off" in names
        assert "cmw_gen_load_arb" in names
        assert "cmw_gen_configure_arb" in names

    def test_analyzer_tools_present(self):
        """Verify analyzer tools are present."""
        tools = get_tools()
        names = {t.name for t in tools}
        assert "cmw_meas_configure_power" in names
        assert "cmw_meas_set_frequency" in names
        assert "cmw_meas_set_expected_power" in names
        assert "cmw_meas_trigger" in names
        assert "cmw_meas_fetch_power" in names

    def test_lte_signaling_tools_present(self):
        """Verify LTE signaling tools are present."""
        tools = get_tools()
        names = {t.name for t in tools}
        assert "cmw_lte_configure_cell" in names
        assert "cmw_lte_cell_on" in names
        assert "cmw_lte_cell_off" in names
        assert "cmw_lte_get_connection_state" in names
        assert "cmw_lte_configure_nas" in names
        assert "cmw_lte_configure_cdrx" in names

    def test_lte_measurement_tools_present(self):
        """Verify LTE measurement tools are present."""
        tools = get_tools()
        names = {t.name for t in tools}
        assert "cmw_lte_meas_configure" in names
        assert "cmw_lte_meas_trigger" in names
        assert "cmw_lte_meas_fetch_power" in names
        assert "cmw_lte_meas_fetch_evm" in names
        assert "cmw_lte_meas_fetch_aclr" in names
        assert "cmw_lte_meas_fetch_sem" in names
        assert "cmw_lte_meas_fetch_all" in names

    def test_scpi_tools_present(self):
        """Verify raw SCPI tools are present."""
        tools = get_tools()
        names = {t.name for t in tools}
        assert "cmw_scpi_send" in names
        assert "cmw_scpi_query" in names
        assert "cmw_reset" in names
        assert "cmw_preset" in names

    def test_template_tools_present(self):
        """Verify template tools are present."""
        tools = get_tools()
        names = {t.name for t in tools}
        assert "cmw_list_templates" in names
        assert "cmw_load_template" in names
        assert "cmw_apply_template" in names

    def test_limit_tools_present(self):
        """Verify limit tools are present."""
        tools = get_tools()
        names = {t.name for t in tools}
        assert "cmw_define_limit" in names
        assert "cmw_check_limits" in names
        assert "cmw_clear_limits" in names
        assert "cmw_list_limits" in names

    def test_state_tools_present(self):
        """Verify state tools are present."""
        tools = get_tools()
        names = {t.name for t in tools}
        assert "cmw_save_state" in names
        assert "cmw_load_state" in names
        assert "cmw_get_full_state" in names

    def test_unique_tool_names(self):
        """Verify all tool names are unique."""
        tools = get_tools()
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), "Duplicate tool names found"


class TestToolHandlers:
    """Test tool handler dispatch."""

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        """Unknown tool should return error with isError=True."""
        result = await handle_tool("cmw_nonexistent", {})
        assert isinstance(result, CallToolResult)
        assert result.isError is True
        assert len(result.content) == 1
        assert "Error" in result.content[0].text or "Unknown" in result.content[0].text

    @pytest.mark.asyncio
    async def test_list_templates_handler(self):
        """List templates should work without connection."""
        result = await handle_tool("cmw_list_templates", {})
        assert isinstance(result, CallToolResult)
        assert result.isError is False
        assert len(result.content) == 1
        assert "templates" in result.content[0].text

    @pytest.mark.asyncio
    async def test_list_limits_handler(self):
        """List limits should work without connection."""
        result = await handle_tool("cmw_list_limits", {})
        assert isinstance(result, CallToolResult)
        assert result.isError is False
        assert len(result.content) == 1
        assert "limits" in result.content[0].text

    @pytest.mark.asyncio
    async def test_clear_limits_handler(self):
        """Clear limits should work without connection."""
        result = await handle_tool("cmw_clear_limits", {})
        assert isinstance(result, CallToolResult)
        assert result.isError is False
        assert len(result.content) == 1
        assert "cleared" in result.content[0].text

    @pytest.mark.asyncio
    async def test_define_and_check_limits(self):
        """Test define and check limits workflow."""
        # Define a limit
        result = await handle_tool(
            "cmw_define_limit",
            {
                "name": "test_power_limit",
                "parameter": "power_dbm",
                "max_value": 23.0,
                "min_value": 20.0,
                "unit": "dBm",
            },
        )
        assert result.isError is False
        assert "ok" in result.content[0].text

        # Check passing measurement
        result = await handle_tool(
            "cmw_check_limits",
            {
                "measurements": {"power_dbm": 21.5},
            },
        )
        assert result.isError is False
        text = result.content[0].text.lower()
        assert "true" in text or "passed" in text

        # Check failing measurement
        result = await handle_tool(
            "cmw_check_limits",
            {
                "measurements": {"power_dbm": 25.0},
            },
        )
        assert result.isError is False
        text = result.content[0].text.lower()
        assert "false" in text or "failed" in text

        # Clean up
        await handle_tool("cmw_clear_limits", {})

    @pytest.mark.asyncio
    async def test_load_template_handler(self):
        """Test loading a template."""
        result = await handle_tool(
            "cmw_load_template",
            {
                "template_name": "gprf_power",
            },
        )
        assert result.isError is False
        assert "ok" in result.content[0].text

    @pytest.mark.asyncio
    async def test_load_template_with_params(self):
        """Test loading a template with parameter overrides."""
        result = await handle_tool(
            "cmw_load_template",
            {
                "template_name": "lte_tx_power",
                "parameters": {"band": 7, "bandwidth_mhz": 20.0},
            },
        )
        assert result.isError is False
        assert "ok" in result.content[0].text

    @pytest.mark.asyncio
    async def test_load_wlan_tx_template(self):
        """Test loading the WLAN TX template."""
        result = await handle_tool(
            "cmw_load_template",
            {
                "template_name": "wlan_tx",
            },
        )
        assert result.isError is False
        assert "ok" in result.content[0].text

    @pytest.mark.asyncio
    async def test_load_unknown_template(self):
        """Test loading an unknown template returns isError=True."""
        result = await handle_tool(
            "cmw_load_template",
            {
                "template_name": "nonexistent",
            },
        )
        assert isinstance(result, CallToolResult)
        assert result.isError is True
        assert "Error" in result.content[0].text

    @pytest.mark.asyncio
    async def test_error_responses_have_is_error_flag(self):
        """Verify all error responses set isError=True (Issue #6)."""
        # Unknown tool
        result = await handle_tool("cmw_nonexistent", {})
        assert result.isError is True

        # Unknown template
        result = await handle_tool(
            "cmw_load_template",
            {
                "template_name": "bad_template",
            },
        )
        assert result.isError is True

    @pytest.mark.asyncio
    async def test_success_responses_have_is_error_false(self):
        """Verify success responses set isError=False (Issue #6)."""
        result = await handle_tool("cmw_list_templates", {})
        assert result.isError is False

        result = await handle_tool("cmw_list_limits", {})
        assert result.isError is False

    @pytest.mark.asyncio
    async def test_connection_error_returns_is_error(self):
        """Connection failures should return isError=True."""
        # Trying to connect to a non-existent host should fail
        result = await handle_tool(
            "cmw_connect",
            {
                "host": "192.0.2.1",  # RFC 5737 TEST-NET, guaranteed unreachable
                "port": 5025,
            },
        )
        assert isinstance(result, CallToolResult)
        assert result.isError is True
        assert "Error" in result.content[0].text


class TestAsyncLocks:
    """Test that asyncio locks protect shared state (Issue #4)."""

    @pytest.mark.asyncio
    async def test_concurrent_template_operations(self):
        """Templates should be safe under concurrent access."""

        async def load_template(name):
            return await handle_tool(
                "cmw_load_template",
                {
                    "template_name": name,
                },
            )

        # Run multiple template loads concurrently
        results = await asyncio.gather(
            load_template("gprf_power"),
            load_template("lte_tx_power"),
            load_template("wlan_tx"),
        )

        # All should succeed (no race conditions)
        for result in results:
            assert isinstance(result, CallToolResult)
            assert result.isError is False
            assert "ok" in result.content[0].text

    @pytest.mark.asyncio
    async def test_concurrent_limit_operations(self):
        """Limits should be safe under concurrent access."""
        # Clean up first
        await handle_tool("cmw_clear_limits", {})

        async def define_limit(name, param, max_val, min_val):
            return await handle_tool(
                "cmw_define_limit",
                {
                    "name": name,
                    "parameter": param,
                    "max_value": max_val,
                    "min_value": min_val,
                },
            )

        # Define multiple limits concurrently
        results = await asyncio.gather(
            define_limit("limit_a", "power_dbm", 30.0, 10.0),
            define_limit("limit_b", "evm_percent", 5.0, 0.0),
            define_limit("limit_c", "freq_error_hz", 100.0, -100.0),
        )

        for result in results:
            assert isinstance(result, CallToolResult)
            assert result.isError is False

        # List should show all limits
        list_result = await handle_tool("cmw_list_limits", {})
        assert list_result.isError is False

        # Clean up
        await handle_tool("cmw_clear_limits", {})


class TestPresetTimeout:
    """Test configurable timeout for preset/reset (Issue #14)."""

    @pytest.mark.asyncio
    async def test_preset_timeout_config(self):
        """Verify preset_timeout is available in config."""
        from rs_cmw500_mcp.config import CMWSettings

        settings = CMWSettings()
        assert hasattr(settings, "preset_timeout")
        assert settings.preset_timeout == 60.0

    @pytest.mark.asyncio
    async def test_preset_timeout_customizable(self):
        """Verify preset_timeout can be customized."""
        import os

        old = os.environ.get("CMW_PRESET_TIMEOUT")
        try:
            os.environ["CMW_PRESET_TIMEOUT"] = "120.0"
            from rs_cmw500_mcp.config import CMWSettings

            settings = CMWSettings()
            assert settings.preset_timeout == 120.0
        finally:
            if old is not None:
                os.environ["CMW_PRESET_TIMEOUT"] = old
            else:
                os.environ.pop("CMW_PRESET_TIMEOUT", None)

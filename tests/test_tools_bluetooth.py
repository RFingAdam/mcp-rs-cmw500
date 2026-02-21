"""Tests for Bluetooth MCP tool handlers."""

from unittest.mock import AsyncMock, patch

import pytest

from rs_cmw500_mcp.tools import handle_tool


@pytest.fixture
def mock_cmw():
    """Create a mock CMW500 driver."""
    cmw = AsyncMock()
    cmw.is_connected = True
    cmw.bt_configure = AsyncMock()
    cmw.bt_set_technology = AsyncMock()
    cmw.bt_set_ble_mode = AsyncMock()
    cmw.bt_set_packet_type = AsyncMock()
    cmw.bt_set_frequency = AsyncMock()
    cmw.bt_set_expected_power = AsyncMock()
    cmw.bt_trigger = AsyncMock()
    cmw.bt_fetch_power = AsyncMock(return_value={"power_dbm": 5.0})
    cmw.bt_fetch_modulation = AsyncMock(return_value={"devm_rms_percent": 3.5})
    cmw.bt_fetch_frequency = AsyncMock(return_value={"initial_offset_khz": 1.2})
    cmw.bt_fetch_all = AsyncMock(
        return_value={
            "power": {},
            "modulation": {},
            "frequency": {},
        }
    )
    return cmw


class TestBTTools:
    """Test Bluetooth MCP tool handlers."""

    @pytest.mark.asyncio
    async def test_bt_configure(self, mock_cmw):
        """cmw_bt_configure should call driver."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool(
                "cmw_bt_configure",
                {
                    "technology": "LENergy",
                    "ble_mode": "LE1M",
                    "frequency_hz": 2.402e9,
                    "expected_power_dbm": 10.0,
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_set_technology(self, mock_cmw):
        """cmw_bt_set_technology should call driver."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool(
                "cmw_bt_set_technology",
                {
                    "technology": "LENergy",
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_set_ble_mode(self, mock_cmw):
        """cmw_bt_set_ble_mode should call driver."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool(
                "cmw_bt_set_ble_mode",
                {
                    "ble_mode": "LE2M",
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_set_packet_type(self, mock_cmw):
        """cmw_bt_set_packet_type should call driver."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool(
                "cmw_bt_set_packet_type",
                {
                    "packet_type": "DH5",
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_set_frequency(self, mock_cmw):
        """cmw_bt_set_frequency should call driver."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool(
                "cmw_bt_set_frequency",
                {
                    "frequency_hz": 2.426e9,
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_set_expected_power(self, mock_cmw):
        """cmw_bt_set_expected_power should call driver."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool(
                "cmw_bt_set_expected_power",
                {
                    "power_dbm": 5.0,
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_trigger(self, mock_cmw):
        """cmw_bt_trigger should call driver."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool("cmw_bt_trigger", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_fetch_power(self, mock_cmw):
        """cmw_bt_fetch_power should return results."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool("cmw_bt_fetch_power", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_fetch_modulation(self, mock_cmw):
        """cmw_bt_fetch_modulation should return results."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool("cmw_bt_fetch_modulation", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_fetch_frequency(self, mock_cmw):
        """cmw_bt_fetch_frequency should return results."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool("cmw_bt_fetch_frequency", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_fetch_all(self, mock_cmw):
        """cmw_bt_fetch_all should return combined results."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool("cmw_bt_fetch_all", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_tools_connection_error(self):
        """BT tools should handle connection errors."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            side_effect=ConnectionError("No connection"),
        ):
            result = await handle_tool("cmw_bt_trigger", {})
            assert result.isError is True

    @pytest.mark.asyncio
    async def test_bt_configure_defaults(self, mock_cmw):
        """cmw_bt_configure should use defaults when no args given."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool("cmw_bt_configure", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_bt_configure_with_meas_instance(self, mock_cmw):
        """cmw_bt_configure should pass meas_instance."""
        with patch(
            "rs_cmw500_mcp.tools.bluetooth._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool(
                "cmw_bt_configure",
                {
                    "meas_instance": 2,
                },
            )
            assert result.isError is False

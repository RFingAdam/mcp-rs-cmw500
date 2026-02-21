"""Tests for WLAN MCP tool handlers."""

from unittest.mock import AsyncMock, patch

import pytest

from rs_cmw500_mcp.tools import handle_tool


@pytest.fixture
def mock_cmw():
    """Create a mock CMW500 driver."""
    cmw = AsyncMock()
    cmw.is_connected = True
    cmw.wlan_configure = AsyncMock()
    cmw.wlan_set_standard = AsyncMock()
    cmw.wlan_set_bandwidth = AsyncMock()
    cmw.wlan_set_frequency = AsyncMock()
    cmw.wlan_set_expected_power = AsyncMock()
    cmw.wlan_trigger = AsyncMock()
    cmw.wlan_fetch_power = AsyncMock(return_value={"power_dbm": 20.0})
    cmw.wlan_fetch_evm = AsyncMock(return_value={"evm_all_carriers_db": -30.0})
    cmw.wlan_fetch_spectrum_flatness = AsyncMock(return_value={"passed": True})
    cmw.wlan_fetch_frequency_error = AsyncMock(return_value={"frequency_error_hz": 10.0})
    cmw.wlan_fetch_all = AsyncMock(
        return_value={"power": {}, "evm": {}, "spectrum_flatness": {}, "frequency_error": {}}
    )
    return cmw


class TestWLANTools:
    """Test WLAN MCP tool handlers."""

    @pytest.mark.asyncio
    async def test_wlan_configure(self, mock_cmw):
        """cmw_wlan_configure should call driver."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool(
                "cmw_wlan_configure",
                {
                    "standard": "AX",
                    "bandwidth": "BW80",
                    "frequency_hz": 5.18e9,
                    "expected_power_dbm": 20.0,
                },
            )
            assert result.isError is False
            mock_cmw.wlan_configure.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_wlan_set_standard(self, mock_cmw):
        """cmw_wlan_set_standard should call driver."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool(
                "cmw_wlan_set_standard",
                {
                    "standard": "AC",
                },
            )
            assert result.isError is False
            mock_cmw.wlan_set_standard.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_wlan_set_bandwidth(self, mock_cmw):
        """cmw_wlan_set_bandwidth should call driver."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool(
                "cmw_wlan_set_bandwidth",
                {
                    "bandwidth": "BW40",
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_wlan_set_frequency(self, mock_cmw):
        """cmw_wlan_set_frequency should call driver."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool(
                "cmw_wlan_set_frequency",
                {
                    "frequency_hz": 5.18e9,
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_wlan_set_expected_power(self, mock_cmw):
        """cmw_wlan_set_expected_power should call driver."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool(
                "cmw_wlan_set_expected_power",
                {
                    "power_dbm": 15.0,
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_wlan_trigger(self, mock_cmw):
        """cmw_wlan_trigger should call driver."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool("cmw_wlan_trigger", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_wlan_fetch_power(self, mock_cmw):
        """cmw_wlan_fetch_power should return results."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool("cmw_wlan_fetch_power", {})
            assert result.isError is False
            assert "power_dbm" in result.content[0].text

    @pytest.mark.asyncio
    async def test_wlan_fetch_evm(self, mock_cmw):
        """cmw_wlan_fetch_evm should return results."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool("cmw_wlan_fetch_evm", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_wlan_fetch_spectrum_flatness(self, mock_cmw):
        """cmw_wlan_fetch_spectrum_flatness should return results."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool("cmw_wlan_fetch_spectrum_flatness", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_wlan_fetch_frequency_error(self, mock_cmw):
        """cmw_wlan_fetch_frequency_error should return results."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool("cmw_wlan_fetch_frequency_error", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_wlan_fetch_all(self, mock_cmw):
        """cmw_wlan_fetch_all should return combined results."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool("cmw_wlan_fetch_all", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_wlan_configure_with_meas_instance(self, mock_cmw):
        """cmw_wlan_configure should pass meas_instance."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool(
                "cmw_wlan_configure",
                {
                    "meas_instance": 2,
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_wlan_tools_connection_error(self):
        """WLAN tools should handle connection errors."""
        with patch(
            "rs_cmw500_mcp.tools.wlan._get_cmw",
            side_effect=ConnectionError("No connection"),
        ):
            result = await handle_tool("cmw_wlan_trigger", {})
            assert result.isError is True

    @pytest.mark.asyncio
    async def test_wlan_configure_defaults(self, mock_cmw):
        """cmw_wlan_configure should use defaults when no args given."""
        with patch("rs_cmw500_mcp.tools.wlan._get_cmw", return_value=mock_cmw):
            result = await handle_tool("cmw_wlan_configure", {})
            assert result.isError is False

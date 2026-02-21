"""Tests for advanced GPRF driver methods and tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rs_cmw500_mcp.tools import handle_tool


@pytest.fixture
def mock_scpi():
    """Create a mock SCPI connection."""
    scpi = AsyncMock()
    scpi.send = AsyncMock()
    scpi.query = AsyncMock(return_value="0,0.0")
    return scpi


@pytest.fixture
def cmw_driver(mock_scpi):
    """Create a CMW500Driver with mock SCPI."""
    from rs_cmw500_mcp.driver.cmw500_driver import CMW500Driver

    driver = CMW500Driver.__new__(CMW500Driver)
    driver._scpi = mock_scpi
    driver._generator_on = False
    driver._cell_on = False
    driver._safety = MagicMock()
    return driver


@pytest.fixture
def mock_cmw():
    """Create a mock CMW500 driver for tool tests."""
    cmw = AsyncMock()
    cmw.is_connected = True
    cmw.meas_set_trigger_source = AsyncMock()
    cmw.meas_set_trigger_threshold = AsyncMock()
    cmw.meas_set_power_filter = AsyncMock()
    cmw.gen_set_baseband_mode = AsyncMock()
    cmw.meas_set_user_margin = AsyncMock()
    cmw.gen_set_port = AsyncMock()
    cmw.meas_set_port = AsyncMock()
    cmw.system_all_off = AsyncMock()
    return cmw


class TestAdvancedGPRFDriver:
    """Test advanced GPRF driver SCPI commands."""

    @pytest.mark.asyncio
    async def test_meas_set_trigger_source(self, cmw_driver, mock_scpi):
        """meas_set_trigger_source should send correct SCPI."""
        await cmw_driver.meas_set_trigger_source("IF Power")
        mock_scpi.send.assert_called_with("TRIGger:GPRF:MEAS1:POWer:SOURce 'IF Power'")

    @pytest.mark.asyncio
    async def test_meas_set_trigger_threshold(self, cmw_driver, mock_scpi):
        """meas_set_trigger_threshold should send correct SCPI."""
        await cmw_driver.meas_set_trigger_threshold(-20.0)
        mock_scpi.send.assert_called_with("TRIGger:GPRF:MEAS1:POWer:THReshold -20.0")

    @pytest.mark.asyncio
    async def test_meas_set_power_filter(self, cmw_driver, mock_scpi):
        """meas_set_power_filter should send filter type and BW."""
        await cmw_driver.meas_set_power_filter("GAUSs", 1e6)
        calls = [str(c) for c in mock_scpi.send.call_args_list]
        assert any("FILTer:TYPE" in c for c in calls)
        assert any("FILTer:BWIDth" in c for c in calls)

    @pytest.mark.asyncio
    async def test_meas_set_power_filter_no_bw(self, cmw_driver, mock_scpi):
        """meas_set_power_filter without BW should only set type."""
        await cmw_driver.meas_set_power_filter("NONE")
        assert mock_scpi.send.call_count == 1

    @pytest.mark.asyncio
    async def test_gen_set_baseband_mode(self, cmw_driver, mock_scpi):
        """gen_set_baseband_mode should send correct SCPI."""
        await cmw_driver.gen_set_baseband_mode("ARB")
        mock_scpi.send.assert_called_with("SOURce:GPRF:GENerator1:BBMode ARB")

    @pytest.mark.asyncio
    async def test_meas_set_user_margin(self, cmw_driver, mock_scpi):
        """meas_set_user_margin should send correct SCPI."""
        await cmw_driver.meas_set_user_margin(3.0)
        mock_scpi.send.assert_called_with("CONFigure:GPRF:MEAS1:RFSettings:UMARgin 3.0")

    @pytest.mark.asyncio
    async def test_gen_set_port(self, cmw_driver, mock_scpi):
        """gen_set_port should send correct SCPI."""
        await cmw_driver.gen_set_port("RF1COM")
        mock_scpi.send.assert_called_with("ROUTe:GPRF:GENerator1:SCENario:SPATh RF1COM")

    @pytest.mark.asyncio
    async def test_meas_set_port(self, cmw_driver, mock_scpi):
        """meas_set_port should send correct SCPI."""
        await cmw_driver.meas_set_port("RF2COM")
        mock_scpi.send.assert_called_with("ROUTe:GPRF:MEAS1:SCENario:SPATh RF2COM")

    @pytest.mark.asyncio
    async def test_system_all_off(self, cmw_driver, mock_scpi):
        """system_all_off should turn off generators and measurements."""
        await cmw_driver.system_all_off()
        calls = [str(c) for c in mock_scpi.send.call_args_list]
        assert any("GENerator:ALL:OFF" in c for c in calls)
        assert any("MEASurement:ALL:OFF" in c for c in calls)
        assert cmw_driver._generator_on is False


class TestAdvancedGPRFTools:
    """Test advanced GPRF MCP tool handlers."""

    @pytest.mark.asyncio
    async def test_meas_set_trigger_tool(self, mock_cmw):
        """cmw_meas_set_trigger should call driver."""
        with patch(
            "rs_cmw500_mcp.tools.gprf_advanced._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool(
                "cmw_meas_set_trigger",
                {
                    "source": "IF Power",
                    "threshold_dbm": -20.0,
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_gen_set_baseband_mode_tool(self, mock_cmw):
        """cmw_gen_set_baseband_mode should call driver."""
        with patch(
            "rs_cmw500_mcp.tools.gprf_advanced._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool(
                "cmw_gen_set_baseband_mode",
                {
                    "mode": "ARB",
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_system_all_off_tool(self, mock_cmw):
        """cmw_system_all_off should call driver."""
        with patch(
            "rs_cmw500_mcp.tools.gprf_advanced._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool("cmw_system_all_off", {})
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_set_port_tool(self, mock_cmw):
        """cmw_set_port should call driver for gen and analyzer."""
        with patch(
            "rs_cmw500_mcp.tools.gprf_advanced._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool(
                "cmw_set_port",
                {
                    "generator_port": "RF1COM",
                    "analyzer_port": "RF2COM",
                },
            )
            assert result.isError is False

    @pytest.mark.asyncio
    async def test_meas_set_user_margin_tool(self, mock_cmw):
        """cmw_meas_set_user_margin should call driver."""
        with patch(
            "rs_cmw500_mcp.tools.gprf_advanced._get_cmw",
            return_value=mock_cmw,
        ):
            result = await handle_tool(
                "cmw_meas_set_user_margin",
                {
                    "margin_db": 5.0,
                },
            )
            assert result.isError is False

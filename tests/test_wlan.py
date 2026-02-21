"""Tests for WLAN driver methods."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from rs_cmw500_mcp.models.cmw_types import (
    WLANBandwidth,
    WLANMeasConfig,
    WLANStandard,
)


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
    driver._safety.validate_frequency = MagicMock()
    driver._safety.validate_expected_power = MagicMock()
    return driver


class TestWLANDriverMethods:
    """Test WLAN driver SCPI commands."""

    @pytest.mark.asyncio
    async def test_wlan_set_route(self, cmw_driver, mock_scpi):
        """wlan_set_route should send correct SCPI."""
        await cmw_driver.wlan_set_route("SALone", 1)
        mock_scpi.send.assert_called_with("ROUTe:WLAN:MEAS1:SCENario SALone")

    @pytest.mark.asyncio
    async def test_wlan_set_standard(self, cmw_driver, mock_scpi):
        """wlan_set_standard should send correct SCPI."""
        await cmw_driver.wlan_set_standard("AX", 1)
        mock_scpi.send.assert_called_with("CONFigure:WLAN:MEAS1:MEValuation:STANdard AX")

    @pytest.mark.asyncio
    async def test_wlan_set_bandwidth(self, cmw_driver, mock_scpi):
        """wlan_set_bandwidth should send correct SCPI."""
        await cmw_driver.wlan_set_bandwidth("BW80", 1)
        mock_scpi.send.assert_called_with("CONFigure:WLAN:MEAS1:MEValuation:BWIDth BW80")

    @pytest.mark.asyncio
    async def test_wlan_set_frequency(self, cmw_driver, mock_scpi):
        """wlan_set_frequency should validate and send SCPI."""
        await cmw_driver.wlan_set_frequency(5.18e9, 1)
        cmw_driver._safety.validate_frequency.assert_called_with(5.18e9)
        mock_scpi.send.assert_called_with("CONFigure:WLAN:MEAS1:RFSettings:FREQuency 5180000000.0")

    @pytest.mark.asyncio
    async def test_wlan_set_expected_power(self, cmw_driver, mock_scpi):
        """wlan_set_expected_power should validate and send SCPI."""
        await cmw_driver.wlan_set_expected_power(20.0, 1)
        cmw_driver._safety.validate_expected_power.assert_called_with(20.0)
        mock_scpi.send.assert_called_with("CONFigure:WLAN:MEAS1:RFSettings:ENPower 20.0")

    @pytest.mark.asyncio
    async def test_wlan_trigger(self, cmw_driver, mock_scpi):
        """wlan_trigger should send correct SCPI."""
        await cmw_driver.wlan_trigger(1)
        mock_scpi.send.assert_called_with("INITiate:WLAN:MEAS1:MEValuation")

    @pytest.mark.asyncio
    async def test_wlan_configure(self, cmw_driver, mock_scpi):
        """wlan_configure should send all config commands."""
        config = WLANMeasConfig(
            standard=WLANStandard.AX,
            bandwidth=WLANBandwidth.BW80,
            frequency_hz=5.18e9,
            expected_power_dbm=20.0,
        )
        await cmw_driver.wlan_configure(config)
        # Should have sent route, standard, bandwidth, frequency, power
        assert mock_scpi.send.call_count >= 5

    @pytest.mark.asyncio
    async def test_wlan_set_standard_meas_instance_2(self, cmw_driver, mock_scpi):
        """MEAS instance 2 should use MEAS2 in SCPI."""
        await cmw_driver.wlan_set_standard("AC", 2)
        mock_scpi.send.assert_called_with("CONFigure:WLAN:MEAS2:MEValuation:STANdard AC")

    @pytest.mark.asyncio
    async def test_wlan_fetch_power(self, cmw_driver, mock_scpi):
        """wlan_fetch_power should parse SCPI response."""
        mock_scpi.query.return_value = "0,20.5,21.0"
        result = await cmw_driver.wlan_fetch_power(1)
        assert "power_dbm" in result
        mock_scpi.query.assert_called_with("FETCh:WLAN:MEAS1:MEValuation:POWer:CURRent?")

    @pytest.mark.asyncio
    async def test_wlan_fetch_evm(self, cmw_driver, mock_scpi):
        """wlan_fetch_evm should parse SCPI response."""
        mock_scpi.query.return_value = "0,-30.5,-28.2,-35.0"
        result = await cmw_driver.wlan_fetch_evm(1)
        assert "evm_all_carriers_db" in result

    @pytest.mark.asyncio
    async def test_wlan_fetch_spectrum_flatness(self, cmw_driver, mock_scpi):
        """wlan_fetch_spectrum_flatness should parse SCPI response."""
        mock_scpi.query.return_value = "0,PASS,2.5"
        result = await cmw_driver.wlan_fetch_spectrum_flatness(1)
        assert "passed" in result

    @pytest.mark.asyncio
    async def test_wlan_fetch_frequency_error(self, cmw_driver, mock_scpi):
        """wlan_fetch_frequency_error should parse SCPI response."""
        mock_scpi.query.return_value = "0,15.3"
        result = await cmw_driver.wlan_fetch_frequency_error(1)
        assert "frequency_error_hz" in result

    @pytest.mark.asyncio
    async def test_wlan_fetch_all(self, cmw_driver, mock_scpi):
        """wlan_fetch_all should return combined results."""
        mock_scpi.query.return_value = "0,10.0"
        result = await cmw_driver.wlan_fetch_all(1)
        assert "power" in result
        assert "evm" in result
        assert "spectrum_flatness" in result
        assert "frequency_error" in result

    @pytest.mark.asyncio
    async def test_wlan_fetch_power_handles_error(self, cmw_driver, mock_scpi):
        """wlan_fetch_power should handle SCPI errors gracefully."""
        mock_scpi.query.side_effect = OSError("Connection lost")
        result = await cmw_driver.wlan_fetch_power(1)
        # On error, returns empty dict (sparse result)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_wlan_configure_with_custom_meas_instance(self, cmw_driver, mock_scpi):
        """wlan_configure should use custom meas_instance."""
        config = WLANMeasConfig(
            standard=WLANStandard.N,
            bandwidth=WLANBandwidth.BW40,
            frequency_hz=2.437e9,
            meas_instance=3,
        )
        await cmw_driver.wlan_configure(config)
        # Verify MEAS3 is used in at least one call
        calls = [str(c) for c in mock_scpi.send.call_args_list]
        assert any("MEAS3" in c for c in calls)

"""Tests for Bluetooth/BLE driver methods."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from rs_cmw500_mcp.models.cmw_types import (
    BLEMode,
    BTMeasConfig,
    BTPacketType,
    BTTechnology,
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


class TestBTDriverMethods:
    """Test Bluetooth driver SCPI commands."""

    @pytest.mark.asyncio
    async def test_bt_set_route(self, cmw_driver, mock_scpi):
        """bt_set_route should send correct SCPI."""
        await cmw_driver.bt_set_route("SALone", 1)
        mock_scpi.send.assert_called_with("ROUTe:BLUetooth:MEAS1:SCENario SALone")

    @pytest.mark.asyncio
    async def test_bt_set_technology_le(self, cmw_driver, mock_scpi):
        """bt_set_technology should send LE SCPI."""
        await cmw_driver.bt_set_technology("LENergy", 1)
        mock_scpi.send.assert_called_with(
            "CONFigure:BLUetooth:MEAS1:MEValuation:TECHnology LENergy"
        )

    @pytest.mark.asyncio
    async def test_bt_set_technology_classic(self, cmw_driver, mock_scpi):
        """bt_set_technology should send Classic SCPI."""
        await cmw_driver.bt_set_technology("CLASsic", 1)
        mock_scpi.send.assert_called_with(
            "CONFigure:BLUetooth:MEAS1:MEValuation:TECHnology CLASsic"
        )

    @pytest.mark.asyncio
    async def test_bt_set_ble_mode(self, cmw_driver, mock_scpi):
        """bt_set_ble_mode should send correct SCPI."""
        await cmw_driver.bt_set_ble_mode("LE2M", 1)
        mock_scpi.send.assert_called_with("CONFigure:BLUetooth:MEAS1:MEValuation:BURSt:TYPE LE2M")

    @pytest.mark.asyncio
    async def test_bt_set_packet_type(self, cmw_driver, mock_scpi):
        """bt_set_packet_type should send correct SCPI."""
        await cmw_driver.bt_set_packet_type("DH5", 1)
        mock_scpi.send.assert_called_with("CONFigure:BLUetooth:MEAS1:MEValuation:PACKet:TYPE DH5")

    @pytest.mark.asyncio
    async def test_bt_set_frequency(self, cmw_driver, mock_scpi):
        """bt_set_frequency should validate and send SCPI."""
        await cmw_driver.bt_set_frequency(2.402e9, 1)
        cmw_driver._safety.validate_frequency.assert_called_with(2.402e9)
        mock_scpi.send.assert_called_with(
            "CONFigure:BLUetooth:MEAS1:RFSettings:FREQuency 2402000000.0"
        )

    @pytest.mark.asyncio
    async def test_bt_set_expected_power(self, cmw_driver, mock_scpi):
        """bt_set_expected_power should validate and send SCPI."""
        await cmw_driver.bt_set_expected_power(10.0, 1)
        cmw_driver._safety.validate_expected_power.assert_called_with(10.0)
        mock_scpi.send.assert_called_with("CONFigure:BLUetooth:MEAS1:RFSettings:ENPower 10.0")

    @pytest.mark.asyncio
    async def test_bt_trigger(self, cmw_driver, mock_scpi):
        """bt_trigger should send correct SCPI."""
        await cmw_driver.bt_trigger(1)
        mock_scpi.send.assert_called_with("INITiate:BLUetooth:MEAS1:MEValuation")

    @pytest.mark.asyncio
    async def test_bt_configure_le(self, cmw_driver, mock_scpi):
        """bt_configure for LE should send all config commands."""
        config = BTMeasConfig(
            technology=BTTechnology.LE,
            ble_mode=BLEMode.LE_1M,
            frequency_hz=2.402e9,
            expected_power_dbm=10.0,
        )
        await cmw_driver.bt_configure(config)
        assert mock_scpi.send.call_count >= 5

    @pytest.mark.asyncio
    async def test_bt_configure_classic(self, cmw_driver, mock_scpi):
        """bt_configure for Classic should send packet type."""
        config = BTMeasConfig(
            technology=BTTechnology.CLASSIC,
            packet_type=BTPacketType.DH1,
            frequency_hz=2.402e9,
            expected_power_dbm=10.0,
        )
        await cmw_driver.bt_configure(config)
        calls = [str(c) for c in mock_scpi.send.call_args_list]
        assert any("PACKet:TYPE" in c for c in calls)

    @pytest.mark.asyncio
    async def test_bt_fetch_power(self, cmw_driver, mock_scpi):
        """bt_fetch_power should parse SCPI response."""
        mock_scpi.query.return_value = "0,10.5,12.0,5.2"
        result = await cmw_driver.bt_fetch_power(1)
        assert "power_dbm" in result

    @pytest.mark.asyncio
    async def test_bt_fetch_modulation(self, cmw_driver, mock_scpi):
        """bt_fetch_modulation should parse DEVM."""
        mock_scpi.query.return_value = "0,3.5,5.2,4.8"
        result = await cmw_driver.bt_fetch_modulation(1)
        assert "devm_rms_percent" in result

    @pytest.mark.asyncio
    async def test_bt_fetch_frequency(self, cmw_driver, mock_scpi):
        """bt_fetch_frequency should parse frequency data."""
        mock_scpi.query.return_value = "0,1.2,0.5,0.01"
        result = await cmw_driver.bt_fetch_frequency(1)
        assert "initial_offset_khz" in result

    @pytest.mark.asyncio
    async def test_bt_fetch_all(self, cmw_driver, mock_scpi):
        """bt_fetch_all should return combined results."""
        mock_scpi.query.return_value = "0,10.0"
        result = await cmw_driver.bt_fetch_all(1)
        assert "power" in result
        assert "modulation" in result
        assert "frequency" in result

    @pytest.mark.asyncio
    async def test_bt_fetch_power_handles_error(self, cmw_driver, mock_scpi):
        """bt_fetch_power should handle errors gracefully."""
        mock_scpi.query.side_effect = OSError("Connection lost")
        result = await cmw_driver.bt_fetch_power(1)
        # On error, returns empty dict (sparse result)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_bt_meas_instance_2(self, cmw_driver, mock_scpi):
        """MEAS instance 2 should use MEAS2 in SCPI."""
        await cmw_driver.bt_set_technology("LENergy", 2)
        mock_scpi.send.assert_called_with(
            "CONFigure:BLUetooth:MEAS2:MEValuation:TECHnology LENergy"
        )

    @pytest.mark.asyncio
    async def test_bt_configure_sets_route(self, cmw_driver, mock_scpi):
        """bt_configure should include route setup."""
        config = BTMeasConfig(
            technology=BTTechnology.LE,
            ble_mode=BLEMode.LE_1M,
        )
        await cmw_driver.bt_configure(config)
        calls = [str(c) for c in mock_scpi.send.call_args_list]
        assert any("ROUTe:BLUetooth" in c for c in calls)

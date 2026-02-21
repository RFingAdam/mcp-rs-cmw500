"""Tests for CMW500 driver."""

from unittest.mock import AsyncMock

import pytest

from rs_cmw500_mcp.driver.cmw500_driver import CMW500Driver, ConnectionState
from rs_cmw500_mcp.exceptions import SafetyError
from rs_cmw500_mcp.models.cmw_types import (
    ARBRepetition,
    CellConfig,
    MeasRepetition,
    SignalPath,
)
from rs_cmw500_mcp.safety.validators import SafetyLimits


class TestCMW500DriverInit:
    """Test driver initialization."""

    def test_default_init(self):
        driver = CMW500Driver()
        assert driver.host == "127.0.0.1"
        assert driver.port == 5025
        assert driver.is_connected is False
        assert driver.info is None
        assert driver._state == ConnectionState.DISCONNECTED

    def test_custom_init(self):
        driver = CMW500Driver(
            host="192.168.1.100",
            port=5025,
            timeout=10.0,
            command_timeout=60.0,
        )
        assert driver.host == "192.168.1.100"
        assert driver.port == 5025

    def test_custom_safety_limits(self):
        limits = SafetyLimits(max_generator_power_dbm=-10.0)
        driver = CMW500Driver(safety_limits=limits)
        assert driver._safety.limits.max_generator_power_dbm == -10.0


class TestCMW500DriverSystem:
    """Test system commands."""

    @pytest.fixture
    def driver(self, mock_scpi_socket):
        """Create driver with mocked SCPI socket."""
        d = CMW500Driver()
        d._scpi = mock_scpi_socket
        d._state = ConnectionState.CONNECTED
        return d

    @pytest.mark.asyncio
    async def test_identify(self, driver):
        """Test identify command."""
        driver._scpi.query = AsyncMock(
            return_value="Rohde&Schwarz,CMW500,1234567,V3.8.10"
        )
        info = await driver.identify()
        assert info.manufacturer == "Rohde&Schwarz"
        assert info.model == "CMW500"
        assert info.serial_number == "1234567"
        driver._scpi.query.assert_called_with("*IDN?")

    @pytest.mark.asyncio
    async def test_reset(self, driver):
        """Test reset command."""
        await driver.reset()
        driver._scpi.send.assert_called_with("*RST")
        driver._scpi.wait_opc.assert_called_once()
        assert driver._generator_on is False
        assert driver._cell_on is False

    @pytest.mark.asyncio
    async def test_preset(self, driver):
        """Test preset command."""
        await driver.preset()
        driver._scpi.send.assert_called_with("SYSTem:PRESet")

    @pytest.mark.asyncio
    async def test_get_errors_empty(self, driver):
        """Test get_errors with no errors."""
        driver._scpi.query = AsyncMock(return_value='0,"No error"')
        errors = await driver.get_errors()
        assert errors == []

    @pytest.mark.asyncio
    async def test_get_errors_with_errors(self, driver):
        """Test get_errors with queued errors."""
        driver._scpi.query = AsyncMock(
            side_effect=['-100,"Command error"', '0,"No error"']
        )
        errors = await driver.get_errors()
        assert len(errors) == 1
        assert "Command error" in errors[0]

    @pytest.mark.asyncio
    async def test_query_options(self, driver):
        """Test query_options command."""
        driver._scpi.query = AsyncMock(return_value='"K21","K55","K83"')
        options = await driver.query_options()
        assert "K21" in options
        assert "K55" in options

    @pytest.mark.asyncio
    async def test_get_status(self, driver):
        """Test get_status."""
        status = await driver.get_status()
        assert "connected" in status
        assert "state" in status
        assert "generator_on" in status
        assert "cell_on" in status


class TestCMW500DriverGenerator:
    """Test GPRF Generator commands."""

    @pytest.fixture
    def driver(self, mock_scpi_socket):
        d = CMW500Driver()
        d._scpi = mock_scpi_socket
        d._state = ConnectionState.CONNECTED
        return d

    @pytest.mark.asyncio
    async def test_gen_set_frequency(self, driver):
        """Test setting generator frequency."""
        await driver.gen_set_frequency(1e9)
        driver._scpi.send.assert_called_with(
            "SOURce:GPRF:GENerator1:RFSettings:FREQuency 1000000000.0"
        )

    @pytest.mark.asyncio
    async def test_gen_set_frequency_safety(self, driver):
        """Test frequency safety validation."""
        with pytest.raises(SafetyError):
            await driver.gen_set_frequency(10e9)  # Above 6 GHz max

    @pytest.mark.asyncio
    async def test_gen_set_level(self, driver):
        """Test setting generator level."""
        await driver.gen_set_level(-30.0)
        driver._scpi.send.assert_called_with(
            "SOURce:GPRF:GENerator1:RFSettings:LEVel -30.0"
        )

    @pytest.mark.asyncio
    async def test_gen_set_level_safety(self, driver):
        """Test level safety validation."""
        with pytest.raises(SafetyError):
            await driver.gen_set_level(10.0)  # Above 0 dBm max

    @pytest.mark.asyncio
    async def test_gen_output_on(self, driver):
        """Test generator output on."""
        await driver.gen_output_on()
        driver._scpi.send.assert_called_with("SOURce:GPRF:GENerator1:STATe ON")
        assert driver._generator_on is True

    @pytest.mark.asyncio
    async def test_gen_output_off(self, driver):
        """Test generator output off."""
        driver._generator_on = True
        await driver.gen_output_off()
        driver._scpi.send.assert_called_with("SOURce:GPRF:GENerator1:STATe OFF")
        assert driver._generator_on is False

    @pytest.mark.asyncio
    async def test_gen_load_arb(self, driver):
        """Test loading ARB file."""
        await driver.gen_load_arb("/path/to/waveform.wv")
        driver._scpi.send.assert_called_with(
            "SOURce:GPRF:GENerator1:ARB:FILE '/path/to/waveform.wv'"
        )

    @pytest.mark.asyncio
    async def test_gen_configure_arb(self, driver):
        """Test configuring ARB playback."""
        await driver.gen_configure_arb(ARBRepetition.CONTINUOUS)
        driver._scpi.send.assert_called_with(
            "SOURce:GPRF:GENerator1:ARB:REPetition CONTinuous"
        )


class TestCMW500DriverAnalyzer:
    """Test GPRF Analyzer commands."""

    @pytest.fixture
    def driver(self, mock_scpi_socket):
        d = CMW500Driver()
        d._scpi = mock_scpi_socket
        d._state = ConnectionState.CONNECTED
        return d

    @pytest.mark.asyncio
    async def test_meas_set_frequency(self, driver):
        """Test setting analyzer frequency."""
        await driver.meas_set_frequency(2.4e9)
        driver._scpi.send.assert_called_with(
            "CONFigure:GPRF:MEASurement1:RFSettings:FREQuency 2400000000.0"
        )

    @pytest.mark.asyncio
    async def test_meas_set_expected_power(self, driver):
        """Test setting expected power."""
        await driver.meas_set_expected_power(10.0)
        driver._scpi.send.assert_called_with(
            "CONFigure:GPRF:MEASurement1:RFSettings:ENPower 10.0"
        )

    @pytest.mark.asyncio
    async def test_meas_set_expected_power_safety(self, driver):
        """Test expected power safety."""
        with pytest.raises(SafetyError):
            await driver.meas_set_expected_power(40.0)  # Above 33 dBm

    @pytest.mark.asyncio
    async def test_meas_configure_power(self, driver):
        """Test configuring power measurement."""
        await driver.meas_configure_power(
            statistic_count=20,
            meas_length_s=0.01,
            repetition=MeasRepetition.SINGLESHOT,
        )
        calls = [str(c) for c in driver._scpi.send.call_args_list]
        assert any("SCOunt 20" in c for c in calls)
        assert any("MLENgth 0.01" in c for c in calls)
        assert any("SINGleshot" in c for c in calls)

    @pytest.mark.asyncio
    async def test_meas_trigger_power(self, driver):
        """Test triggering power measurement."""
        await driver.meas_trigger_power()
        driver._scpi.send.assert_called_with(
            "INITiate:GPRF:MEASurement1:POWer"
        )

    @pytest.mark.asyncio
    async def test_meas_fetch_power(self, driver):
        """Test fetching power results."""
        driver._scpi.query = AsyncMock(
            side_effect=[
                "0,-30.5",   # current
                "0,-30.3",   # average
                "0,-29.8",   # maximum
                "0,-31.0",   # minimum
            ]
        )
        result = await driver.meas_fetch_power()
        assert result.current_dbm == pytest.approx(-30.5)
        assert result.average_dbm == pytest.approx(-30.3)
        assert result.maximum_dbm == pytest.approx(-29.8)
        assert result.minimum_dbm == pytest.approx(-31.0)


class TestCMW500DriverSignalPath:
    """Test signal path commands."""

    @pytest.fixture
    def driver(self, mock_scpi_socket):
        d = CMW500Driver()
        d._scpi = mock_scpi_socket
        d._state = ConnectionState.CONNECTED
        return d

    @pytest.mark.asyncio
    async def test_set_signal_path_standalone(self, driver):
        """Test setting standalone signal path."""
        await driver.set_signal_path(SignalPath.STANDALONE)
        driver._scpi.send.assert_called_with(
            "ROUTe:GPRF:MEASurement1:SCENario SALone"
        )

    @pytest.mark.asyncio
    async def test_set_signal_path_cspath(self, driver):
        """Test setting combined signal path."""
        await driver.set_signal_path(SignalPath.CS_PATH)
        driver._scpi.send.assert_called_with(
            "ROUTe:GPRF:MEASurement1:SCENario CSPath"
        )

    @pytest.mark.asyncio
    async def test_get_signal_path(self, driver):
        """Test getting signal path."""
        driver._scpi.query = AsyncMock(return_value="SALone")
        path = await driver.get_signal_path()
        assert path == "SALone"


class TestCMW500DriverLTE:
    """Test LTE signaling commands."""

    @pytest.fixture
    def driver(self, mock_scpi_socket):
        d = CMW500Driver()
        d._scpi = mock_scpi_socket
        d._state = ConnectionState.CONNECTED
        return d

    @pytest.mark.asyncio
    async def test_lte_configure_cell(self, driver):
        """Test LTE cell configuration."""
        config = CellConfig(
            band=7,
            bandwidth_mhz=20.0,
            dl_earfcn=3100,
            dl_level_dbm=-60.0,
        )
        await driver.lte_configure_cell(config)
        calls = [str(c) for c in driver._scpi.send.call_args_list]
        assert any("BANDwidth B200" in c for c in calls)
        assert any("BAND 7" in c for c in calls)
        assert any("CHANnel:DL 3100" in c for c in calls)
        assert any("LEVel -60.0" in c for c in calls)

    @pytest.mark.asyncio
    async def test_lte_cell_on(self, driver):
        """Test LTE cell on."""
        await driver.lte_cell_on()
        driver._scpi.send.assert_called_with("CALL:LTE:SIGN1:CELL:STATe ON")
        assert driver._cell_on is True

    @pytest.mark.asyncio
    async def test_lte_cell_off(self, driver):
        """Test LTE cell off."""
        driver._cell_on = True
        await driver.lte_cell_off()
        driver._scpi.send.assert_called_with("CALL:LTE:SIGN1:CELL:STATe OFF")
        assert driver._cell_on is False

    @pytest.mark.asyncio
    async def test_lte_get_connection_state(self, driver):
        """Test getting LTE connection state."""
        driver._scpi.query = AsyncMock(return_value="CONN")
        state = await driver.lte_get_connection_state()
        assert state == "CONN"

    @pytest.mark.asyncio
    async def test_lte_configure_nas(self, driver):
        """Test NAS configuration."""
        await driver.lte_configure_nas("310", "260")
        calls = [str(c) for c in driver._scpi.send.call_args_list]
        assert any("MCC 310" in c for c in calls)
        assert any("MNC 260" in c for c in calls)

    @pytest.mark.asyncio
    async def test_lte_configure_cdrx(self, driver):
        """Test C-DRX configuration."""
        await driver.lte_configure_cdrx(True)
        driver._scpi.send.assert_called_with(
            "CONFigure:LTE:SIGN1:CONNection:CDRX:ENABle ON"
        )

    @pytest.mark.asyncio
    async def test_lte_get_ue_info(self, driver):
        """Test getting UE info."""
        driver._scpi.query = AsyncMock(
            side_effect=["CONN", "ON"]
        )
        info = await driver.lte_get_ue_info()
        assert info["connection_state"] == "CONN"
        assert info["cell_state"] == "ON"


class TestCMW500DriverLTEMeas:
    """Test LTE measurement commands."""

    @pytest.fixture
    def driver(self, mock_scpi_socket):
        d = CMW500Driver()
        d._scpi = mock_scpi_socket
        d._state = ConnectionState.CONNECTED
        return d

    @pytest.mark.asyncio
    async def test_lte_meas_trigger(self, driver):
        """Test triggering LTE measurement."""
        await driver.lte_meas_trigger()
        driver._scpi.send.assert_called_with(
            "INITiate:LTE:MEAS1:MEValuation"
        )

    @pytest.mark.asyncio
    async def test_lte_meas_fetch_power(self, driver):
        """Test fetching LTE power."""
        driver._scpi.query = AsyncMock(return_value="0,23.5,23.2")
        result = await driver.lte_meas_fetch_power()
        assert result.current_dbm == pytest.approx(23.5)
        assert result.average_dbm == pytest.approx(23.2)

    @pytest.mark.asyncio
    async def test_lte_meas_fetch_evm(self, driver):
        """Test fetching LTE EVM."""
        driver._scpi.query = AsyncMock(return_value="0,2.5,8.1")
        result = await driver.lte_meas_fetch_evm()
        assert result.evm_rms_percent == pytest.approx(2.5)
        assert result.evm_peak_percent == pytest.approx(8.1)

    @pytest.mark.asyncio
    async def test_lte_meas_fetch_aclr(self, driver):
        """Test fetching LTE ACLR."""
        driver._scpi.query = AsyncMock(return_value="0,-35.0,-34.5,-50.0,-49.5")
        result = await driver.lte_meas_fetch_aclr()
        assert result.aclr_minus_db == pytest.approx(-35.0)
        assert result.aclr_plus_db == pytest.approx(-34.5)

    @pytest.mark.asyncio
    async def test_lte_meas_fetch_sem(self, driver):
        """Test fetching LTE SEM."""
        driver._scpi.query = AsyncMock(return_value="0,0,5.2")
        result = await driver.lte_meas_fetch_sem()
        assert result.passed is True
        assert result.margin_db == pytest.approx(5.2)

    @pytest.mark.asyncio
    async def test_lte_meas_fetch_all(self, driver):
        """Test fetching all LTE measurements."""
        driver._scpi.query = AsyncMock(
            side_effect=[
                "0,23.5,23.2",    # power
                "0,2.5,8.1",      # evm
                "0,-35.0,-34.5",  # aclr
                "0,0,5.2",        # sem
            ]
        )
        result = await driver.lte_meas_fetch_all()
        assert "power" in result
        assert "evm" in result
        assert "aclr" in result
        assert "sem" in result


class TestCMW500DriverRawSCPI:
    """Test raw SCPI access."""

    @pytest.fixture
    def driver(self, mock_scpi_socket):
        d = CMW500Driver()
        d._scpi = mock_scpi_socket
        d._state = ConnectionState.CONNECTED
        return d

    @pytest.mark.asyncio
    async def test_scpi_send(self, driver):
        """Test sending raw SCPI."""
        await driver.scpi_send("SYSTem:PRESet")
        driver._scpi.send.assert_called_with("SYSTem:PRESet")

    @pytest.mark.asyncio
    async def test_scpi_query(self, driver):
        """Test querying raw SCPI."""
        driver._scpi.query = AsyncMock(return_value="CMW500")
        result = await driver.scpi_query("*IDN?")
        assert result == "CMW500"

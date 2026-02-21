"""CMW500 driver for Rohde & Schwarz CMW500 via TCP/IP SCPI."""

import logging
from enum import Enum
from typing import Any

from ..exceptions import (
    MeasurementError,
)
from ..models.cmw_types import (
    ACLRResult,
    ARBRepetition,
    CellConfig,
    EVMResult,
    InstrumentInfo,
    LTEBandwidth,
    MeasRepetition,
    PowerResult,
    SEMResult,
    SignalPath,
)
from ..safety.validators import SafetyLimits, SafetyValidator, sanitize_scpi_param
from .scpi_socket import SCPISocket

logger = logging.getLogger(__name__)


def _parse_float(value: str, field_name: str = "value") -> float:
    """
    Parse a string to float with meaningful error messages.

    Args:
        value: String to parse
        field_name: Name of the field for error messages

    Returns:
        Parsed float value

    Raises:
        MeasurementError: If value cannot be parsed as float
    """
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        raise MeasurementError(f"Cannot parse {field_name}: '{value}' is not a valid number", "")


class ConnectionState(Enum):
    """CMW500 connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class CMW500Driver:
    """
    Driver for Rohde & Schwarz CMW500 via TCP/IP SCPI.

    Provides methods organized by subsystem:
    - System: connect, disconnect, identify, reset, preset
    - GPRF Generator: frequency, level, output control, ARB
    - GPRF Analyzer: power measurement, spectrum
    - LTE Signaling: cell config, connection management
    - LTE Measurement: multi-evaluation measurements
    - Route: signal path configuration

    Example:
        async with CMW500Driver("192.168.1.100", 5025) as cmw:
            info = await cmw.identify()
            print(f"Connected to: {info.model}")

            await cmw.gen_set_frequency(1e9)
            await cmw.gen_set_level(-30)
            await cmw.gen_output_on()
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5025,
        timeout: float = 5.0,
        command_timeout: float = 30.0,
        safety_limits: SafetyLimits | None = None,
    ):
        """
        Initialize CMW500 driver.

        Args:
            host: CMW500 hostname or IP address
            port: TCP port (default 5025)
            timeout: Connection timeout in seconds
            command_timeout: Command timeout in seconds
            safety_limits: Custom safety limits (uses defaults if None)
        """
        self.host = host
        self.port = port
        self._scpi = SCPISocket(host, port, timeout, command_timeout)
        self._safety = SafetyValidator(safety_limits)
        self._state = ConnectionState.DISCONNECTED
        self._info: InstrumentInfo | None = None
        self._generator_on = False
        self._cell_on = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to CMW500."""
        return self._scpi.is_connected

    @property
    def info(self) -> InstrumentInfo | None:
        """Get instrument info (available after identify)."""
        return self._info

    # =========================================================================
    # System Commands
    # =========================================================================

    async def connect(self) -> None:
        """
        Connect to CMW500.

        Raises:
            ConnectionError: If connection fails
        """
        self._state = ConnectionState.CONNECTING
        try:
            await self._scpi.connect()
            self._state = ConnectionState.CONNECTED
        except Exception:
            self._state = ConnectionState.ERROR
            raise

    async def disconnect(self) -> None:
        """Disconnect from CMW500."""
        await self._scpi.disconnect()
        self._state = ConnectionState.DISCONNECTED
        self._info = None

    async def identify(self) -> InstrumentInfo:
        """
        Get CMW500 identification.

        Returns:
            InstrumentInfo with manufacturer, model, serial, firmware

        Raises:
            CommunicationError: If query fails
        """
        idn = await self._scpi.query("*IDN?")
        self._info = InstrumentInfo.from_idn(idn)
        return self._info

    async def reset(self) -> None:
        """Reset CMW500 to default state."""
        await self._scpi.send("*RST")
        await self._scpi.wait_opc()
        self._generator_on = False
        self._cell_on = False

    async def preset(self) -> None:
        """Preset CMW500 (full system preset)."""
        await self._scpi.send("SYSTem:PRESet")
        await self._scpi.wait_opc()
        self._generator_on = False
        self._cell_on = False

    async def get_errors(self) -> list[str]:
        """
        Query system error queue.

        Returns:
            List of error strings
        """
        errors = []
        for _ in range(20):  # Max 20 errors to prevent infinite loop
            response = await self._scpi.query("SYSTem:ERRor?")
            if response.startswith("0,") or response.startswith("0,\"No error"):
                break
            errors.append(response)
        return errors

    async def query_options(self) -> list[str]:
        """
        Query installed hardware/software options.

        Returns:
            List of installed option strings
        """
        response = await self._scpi.query("SYSTem:BASE:OPTion:LIST?")
        options = [opt.strip().strip('"') for opt in response.split(",")]
        if self._info:
            self._info.options = options
        return options

    async def get_status(self) -> dict[str, Any]:
        """
        Get comprehensive CMW500 status.

        Returns:
            Dictionary with connection and state information
        """
        status: dict[str, Any] = {
            "connected": self.is_connected,
            "state": self._state.value,
            "address": self._scpi.address,
            "generator_on": self._generator_on,
            "cell_on": self._cell_on,
        }
        if self._info:
            status["instrument"] = self._info.to_dict()
        return status

    # =========================================================================
    # Raw SCPI Access
    # =========================================================================

    async def scpi_send(self, command: str) -> None:
        """Send raw SCPI command."""
        await self._scpi.send(command)

    async def scpi_query(self, command: str) -> str:
        """Send raw SCPI query and return response."""
        return await self._scpi.query(command)

    # =========================================================================
    # GPRF Generator (RF signal output)
    # =========================================================================

    async def gen_set_frequency(self, frequency_hz: float) -> None:
        """
        Set generator output frequency.

        Args:
            frequency_hz: Frequency in Hz

        Raises:
            SafetyError: If frequency exceeds limits
        """
        self._safety.validate_frequency(frequency_hz)
        await self._scpi.send(
            f"SOURce:GPRF:GENerator1:RFSettings:FREQuency {frequency_hz}"
        )

    async def gen_set_level(self, level_dbm: float) -> None:
        """
        Set generator output level.

        Args:
            level_dbm: Output level in dBm

        Raises:
            SafetyError: If level exceeds limits
        """
        self._safety.validate_generator_power(level_dbm)
        await self._scpi.send(
            f"SOURce:GPRF:GENerator1:RFSettings:LEVel {level_dbm}"
        )

    async def gen_set_external_attenuation(self, attenuation_db: float) -> None:
        """
        Set generator external attenuation.

        Args:
            attenuation_db: External attenuation in dB
        """
        await self._scpi.send(
            f"SOURce:GPRF:GENerator1:RFSettings:EATTenuation {attenuation_db}"
        )

    async def gen_output_on(self) -> None:
        """Enable generator RF output."""
        await self._scpi.send("SOURce:GPRF:GENerator1:STATe ON")
        self._generator_on = True

    async def gen_output_off(self) -> None:
        """Disable generator RF output."""
        await self._scpi.send("SOURce:GPRF:GENerator1:STATe OFF")
        self._generator_on = False

    async def gen_load_arb(self, file_path: str) -> None:
        """
        Load ARB waveform file.

        Args:
            file_path: Path to ARB file on CMW500
        """
        sanitize_scpi_param(file_path)
        await self._scpi.send(f"SOURce:GPRF:GENerator1:ARB:FILE '{file_path}'")

    async def gen_configure_arb(
        self, repetition: ARBRepetition = ARBRepetition.CONTINUOUS
    ) -> None:
        """
        Configure ARB waveform playback.

        Args:
            repetition: Waveform repetition mode
        """
        await self._scpi.send(
            f"SOURce:GPRF:GENerator1:ARB:REPetition {repetition.value}"
        )

    # =========================================================================
    # GPRF Analyzer (RF signal analysis)
    # =========================================================================

    async def meas_set_frequency(self, frequency_hz: float) -> None:
        """
        Set analyzer measurement frequency.

        Args:
            frequency_hz: Frequency in Hz

        Raises:
            SafetyError: If frequency exceeds limits
        """
        self._safety.validate_frequency(frequency_hz)
        await self._scpi.send(
            f"CONFigure:GPRF:MEASurement1:RFSettings:FREQuency {frequency_hz}"
        )

    async def meas_set_expected_power(self, power_dbm: float) -> None:
        """
        Set expected input power for analyzer.

        Args:
            power_dbm: Expected power in dBm

        Raises:
            SafetyError: If power exceeds limits
        """
        self._safety.validate_expected_power(power_dbm)
        await self._scpi.send(
            f"CONFigure:GPRF:MEASurement1:RFSettings:ENPower {power_dbm}"
        )

    async def meas_set_external_attenuation(self, attenuation_db: float) -> None:
        """
        Set analyzer external attenuation.

        Args:
            attenuation_db: External attenuation in dB
        """
        await self._scpi.send(
            f"CONFigure:GPRF:MEASurement1:RFSettings:EATTenuation {attenuation_db}"
        )

    async def meas_configure_power(
        self,
        statistic_count: int = 10,
        meas_length_s: float = 0.001,
        repetition: MeasRepetition = MeasRepetition.SINGLESHOT,
    ) -> None:
        """
        Configure GPRF power measurement.

        Args:
            statistic_count: Number of measurements for statistics
            meas_length_s: Measurement length in seconds
            repetition: Measurement repetition mode
        """
        await self._scpi.send(
            f"CONFigure:GPRF:MEASurement1:POWer:SCOunt {statistic_count}"
        )
        await self._scpi.send(
            f"CONFigure:GPRF:MEASurement1:POWer:MLENgth {meas_length_s}"
        )
        await self._scpi.send(
            f"CONFigure:GPRF:MEASurement1:POWer:REPetition {repetition.value}"
        )

    async def meas_configure_spectrum(self) -> dict[str, str]:
        """Configure GPRF spectrum measurement (not yet fully implemented)."""
        logger.warning("Spectrum measurement configuration is a placeholder")
        return {"status": "placeholder", "note": "Spectrum config not yet implemented"}

    async def meas_trigger_power(self) -> None:
        """Initiate GPRF power measurement."""
        await self._scpi.send("INITiate:GPRF:MEASurement1:POWer")

    async def meas_abort_power(self) -> None:
        """Abort GPRF power measurement."""
        await self._scpi.send("ABORt:GPRF:MEASurement1:POWer")

    async def meas_fetch_power(self) -> PowerResult:
        """
        Fetch GPRF power measurement results.

        Returns:
            PowerResult with current, average, max, min power values
        """
        result = PowerResult()

        try:
            response = await self._scpi.query("FETCh:GPRF:MEASurement1:POWer:CURRent?")
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                result.current_dbm = _parse_float(parts[1], "current_power")
        except Exception as e:
            logger.warning(f"Failed to fetch current power: {e}")

        try:
            response = await self._scpi.query("FETCh:GPRF:MEASurement1:POWer:AVERage?")
            parts = response.split(",")
            if len(parts) >= 2:
                result.average_dbm = _parse_float(parts[1], "average_power")
        except Exception as e:
            logger.warning(f"Failed to fetch average power: {e}")

        try:
            response = await self._scpi.query("FETCh:GPRF:MEASurement1:POWer:MAXimum?")
            parts = response.split(",")
            if len(parts) >= 2:
                result.maximum_dbm = _parse_float(parts[1], "maximum_power")
        except Exception as e:
            logger.warning(f"Failed to fetch maximum power: {e}")

        try:
            response = await self._scpi.query("FETCh:GPRF:MEASurement1:POWer:MINimum?")
            parts = response.split(",")
            if len(parts) >= 2:
                result.minimum_dbm = _parse_float(parts[1], "minimum_power")
        except Exception as e:
            logger.warning(f"Failed to fetch minimum power: {e}")

        return result

    async def meas_fetch_spectrum(self) -> dict[str, Any]:
        """
        Fetch spectrum measurement results.

        Returns:
            Dictionary with spectrum data
        """
        # CMW500 spectrum results depend on measurement configuration
        return {"status": "spectrum measurement not yet configured"}

    # =========================================================================
    # Signal Path / Route
    # =========================================================================

    async def set_signal_path(self, scenario: SignalPath = SignalPath.STANDALONE) -> None:
        """
        Set GPRF measurement signal path scenario.

        Args:
            scenario: Signal path scenario
        """
        await self._scpi.send(
            f"ROUTe:GPRF:MEASurement1:SCENario {scenario.value}"
        )

    async def get_signal_path(self) -> str:
        """
        Get current GPRF signal path scenario.

        Returns:
            Signal path scenario string
        """
        return await self._scpi.query("ROUTe:GPRF:MEASurement1:SCENario?")

    # =========================================================================
    # LTE Signaling
    # =========================================================================

    async def lte_configure_cell(self, config: CellConfig) -> None:
        """
        Configure LTE cell parameters.

        Args:
            config: Cell configuration
        """
        self._safety.validate_dl_level(config.dl_level_dbm)

        bw = LTEBandwidth.from_mhz(config.bandwidth_mhz)
        await self._scpi.send(f"CONFigure:LTE:SIGN1:CELL:BANDwidth {bw.value}")
        await self._scpi.send(f"CONFigure:LTE:SIGN1:CELL:BAND {config.band}")
        await self._scpi.send(
            f"CONFigure:LTE:SIGN1:RFSettings:CHANnel:DL {config.dl_earfcn}"
        )
        await self._scpi.send(
            f"CONFigure:LTE:SIGN1:RFSettings:DL:LEVel {config.dl_level_dbm}"
        )

    async def lte_cell_on(self) -> None:
        """Turn on LTE cell (start base station emulation)."""
        await self._scpi.send("CALL:LTE:SIGN1:CELL:STATe ON")
        await self._scpi.wait_opc()
        self._cell_on = True

    async def lte_cell_off(self) -> None:
        """Turn off LTE cell."""
        await self._scpi.send("CALL:LTE:SIGN1:CELL:STATe OFF")
        await self._scpi.wait_opc()
        self._cell_on = False

    async def lte_get_cell_state(self) -> str:
        """
        Get LTE cell state.

        Returns:
            Cell state string (e.g., "ON", "OFF", "ADJ")
        """
        return await self._scpi.query("CALL:LTE:SIGN1:CELL:STATe?")

    async def lte_get_connection_state(self) -> str:
        """
        Get LTE UE connection state.

        Returns:
            Connection state string (e.g., "ATT", "CONN", "IDLE")
        """
        return await self._scpi.query("CALL:LTE:SIGN1:CONNection:STATe?")

    async def lte_configure_nas(self, mcc: str = "001", mnc: str = "01") -> None:
        """
        Configure NAS (Non-Access Stratum) parameters.

        Args:
            mcc: Mobile Country Code
            mnc: Mobile Network Code
        """
        sanitize_scpi_param(mcc)
        sanitize_scpi_param(mnc)
        await self._scpi.send(f"CONFigure:LTE:SIGN1:NAS:MCC {mcc}")
        await self._scpi.send(f"CONFigure:LTE:SIGN1:NAS:MNC {mnc}")

    async def lte_configure_bearer(self) -> None:
        """Configure default EPS bearer (placeholder for expansion)."""
        logger.info("Bearer configuration using defaults")

    async def lte_configure_cdrx(self, enabled: bool = False) -> None:
        """
        Configure Connected DRX (C-DRX).

        Args:
            enabled: Enable or disable C-DRX
        """
        state = "ON" if enabled else "OFF"
        await self._scpi.send(f"CONFigure:LTE:SIGN1:CONNection:CDRX:ENABle {state}")

    async def lte_get_ue_info(self) -> dict[str, str]:
        """
        Get UE (User Equipment) information.

        Returns:
            Dictionary with UE info (connection state, etc.)
        """
        conn_state = await self.lte_get_connection_state()
        cell_state = await self.lte_get_cell_state()
        return {
            "connection_state": conn_state.strip(),
            "cell_state": cell_state.strip(),
        }

    # =========================================================================
    # LTE Measurement
    # =========================================================================

    async def lte_meas_configure(self) -> dict[str, str]:
        """Configure LTE multi-evaluation measurement (not yet fully implemented)."""
        logger.warning("LTE multi-evaluation measurement configuration is a placeholder")
        return {"status": "placeholder", "note": "LTE measurement config not yet implemented"}

    async def lte_meas_trigger(self) -> None:
        """Trigger LTE multi-evaluation measurement."""
        await self._scpi.send("INITiate:LTE:MEAS1:MEValuation")

    async def lte_meas_fetch_power(self) -> PowerResult:
        """
        Fetch LTE TX power measurement.

        Returns:
            PowerResult with power values
        """
        result = PowerResult()
        try:
            response = await self._scpi.query(
                "FETCh:LTE:MEAS1:MEValuation:POWer:CURRent?"
            )
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                result.current_dbm = _parse_float(parts[1], "lte_power")
            if len(parts) >= 3:
                result.average_dbm = _parse_float(parts[2], "lte_avg_power")
        except Exception as e:
            logger.warning(f"Failed to fetch LTE power: {e}")
        return result

    async def lte_meas_fetch_evm(self) -> EVMResult:
        """
        Fetch LTE EVM measurement.

        Returns:
            EVMResult with EVM values
        """
        result = EVMResult()
        try:
            response = await self._scpi.query(
                "FETCh:LTE:MEAS1:MEValuation:MODulation:CURRent?"
            )
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                result.evm_rms_percent = _parse_float(parts[1], "evm_rms")
            if len(parts) >= 3:
                result.evm_peak_percent = _parse_float(parts[2], "evm_peak")
        except Exception as e:
            logger.warning(f"Failed to fetch LTE EVM: {e}")
        return result

    async def lte_meas_fetch_aclr(self) -> ACLRResult:
        """
        Fetch LTE ACLR measurement.

        Returns:
            ACLRResult with ACLR values
        """
        result = ACLRResult()
        try:
            response = await self._scpi.query(
                "FETCh:LTE:MEAS1:MEValuation:ACLR:CURRent?"
            )
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
            if len(parts) >= 3:
                result.aclr_minus_db = _parse_float(parts[1], "aclr_minus")
                result.aclr_plus_db = _parse_float(parts[2], "aclr_plus")
            if len(parts) >= 5:
                result.aclr_minus2_db = _parse_float(parts[3], "aclr_minus2")
                result.aclr_plus2_db = _parse_float(parts[4], "aclr_plus2")
        except Exception as e:
            logger.warning(f"Failed to fetch LTE ACLR: {e}")
        return result

    async def lte_meas_fetch_sem(self) -> SEMResult:
        """
        Fetch LTE SEM (Spectrum Emission Mask) measurement.

        Returns:
            SEMResult with SEM values
        """
        result = SEMResult()
        try:
            response = await self._scpi.query(
                "FETCh:LTE:MEAS1:MEValuation:SEMask:CURRent?"
            )
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                # SEM pass/fail is typically in the first result field
                result.passed = parts[1].strip() in ("0", "PASS")
            if len(parts) >= 3:
                result.margin_db = _parse_float(parts[2], "sem_margin")
        except Exception as e:
            logger.warning(f"Failed to fetch LTE SEM: {e}")
        return result

    async def lte_meas_fetch_frequency_error(self) -> dict[str, Any]:
        """
        Fetch LTE frequency error measurement.

        Returns:
            Dictionary with frequency error data
        """
        try:
            response = await self._scpi.query(
                "FETCh:LTE:MEAS1:MEValuation:FERRor:CURRent?"
            )
            parts = response.split(",")
            result: dict[str, Any] = {"reliability": parts[0].strip() if parts else ""}
            if len(parts) >= 2:
                result["frequency_error_hz"] = _parse_float(parts[1], "freq_error")
            return result
        except Exception as e:
            logger.warning(f"Failed to fetch frequency error: {e}")
            return {"error": str(e)}

    async def lte_meas_fetch_all(self) -> dict[str, Any]:
        """
        Fetch all LTE measurement results.

        Returns:
            Dictionary with all measurement results
        """
        power = await self.lte_meas_fetch_power()
        evm = await self.lte_meas_fetch_evm()
        aclr = await self.lte_meas_fetch_aclr()
        sem = await self.lte_meas_fetch_sem()

        return {
            "power": power.to_dict(),
            "evm": evm.to_dict(),
            "aclr": aclr.to_dict(),
            "sem": sem.to_dict(),
        }

    # =========================================================================
    # Context Manager
    # =========================================================================

    async def __aenter__(self) -> "CMW500Driver":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        # Safety: turn off generator on exit
        if self._generator_on:
            try:
                await self.gen_output_off()
            except Exception:
                pass
        await self.disconnect()

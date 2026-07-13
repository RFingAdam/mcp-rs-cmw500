"""CMW500 driver for Rohde & Schwarz CMW500 via TCP/IP SCPI."""

import asyncio
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
    EblResult,
    EVMResult,
    InstrumentInfo,
    LTEBandwidth,
    MeasRepetition,
    PerResult,
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
        except (OSError, asyncio.TimeoutError) as e:
            self._state = ConnectionState.ERROR
            logger.error(f"Failed to connect to {self.host}:{self.port}: {e}")
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
            if response.startswith("0,") or response.startswith('0,"No error'):
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

    async def scpi_send_opc(self, command: str) -> bool:
        """Send a raw SCPI command and block on *OPC? until it completes."""
        await self._scpi.send(command)
        return await self._scpi.wait_opc()

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
        await self._scpi.send(f"SOURce:GPRF:GENerator1:RFSettings:FREQuency {frequency_hz}")

    async def gen_set_level(self, level_dbm: float) -> None:
        """
        Set generator output level.

        Args:
            level_dbm: Output level in dBm

        Raises:
            SafetyError: If level exceeds limits
        """
        self._safety.validate_generator_power(level_dbm)
        await self._scpi.send(f"SOURce:GPRF:GENerator1:RFSettings:LEVel {level_dbm}")

    async def gen_set_external_attenuation(self, attenuation_db: float) -> None:
        """
        Set generator external attenuation.

        Args:
            attenuation_db: External attenuation in dB
        """
        await self._scpi.send(f"SOURce:GPRF:GENerator1:RFSettings:EATTenuation {attenuation_db}")

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

    async def gen_configure_arb(self, repetition: ARBRepetition = ARBRepetition.CONTINUOUS) -> None:
        """
        Configure ARB waveform playback.

        Args:
            repetition: Waveform repetition mode
        """
        await self._scpi.send(f"SOURce:GPRF:GENerator1:ARB:REPetition {repetition.value}")

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
        await self._scpi.send(f"CONFigure:GPRF:MEASurement1:RFSettings:FREQuency {frequency_hz}")

    async def meas_set_expected_power(self, power_dbm: float) -> None:
        """
        Set expected input power for analyzer.

        Args:
            power_dbm: Expected power in dBm

        Raises:
            SafetyError: If power exceeds limits
        """
        self._safety.validate_expected_power(power_dbm)
        await self._scpi.send(f"CONFigure:GPRF:MEASurement1:RFSettings:ENPower {power_dbm}")

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
        await self._scpi.send(f"CONFigure:GPRF:MEASurement1:POWer:SCOunt {statistic_count}")
        await self._scpi.send(f"CONFigure:GPRF:MEASurement1:POWer:MLENgth {meas_length_s}")
        await self._scpi.send(f"CONFigure:GPRF:MEASurement1:POWer:REPetition {repetition.value}")

    async def meas_configure_spectrum(
        self,
        center_freq_hz: float | None = None,
        span_hz: float = 100e6,
        rbw_hz: float = 100e3,
        detector: str = "RMS",
    ) -> dict[str, str]:
        """Configure GPRF spectrum measurement.

        Args:
            center_freq_hz: Center frequency in Hz (uses current if None)
            span_hz: Frequency span in Hz (default 100 MHz)
            rbw_hz: Resolution bandwidth in Hz (default 100 kHz)
            detector: Detector type (RMS, PEAK, etc.)
        """
        if center_freq_hz is not None:
            await self._scpi.send(
                f"CONFigure:GPRF:MEASurement1:SPECtrum:FREQuency:CENTer {center_freq_hz}"
            )
        await self._scpi.send(f"CONFigure:GPRF:MEASurement1:SPECtrum:FREQuency:SPAN {span_hz}")
        await self._scpi.send(f"CONFigure:GPRF:MEASurement1:SPECtrum:BWIDth {rbw_hz}")
        sanitize_scpi_param(detector)
        await self._scpi.send(f"CONFigure:GPRF:MEASurement1:SPECtrum:DETector {detector}")
        return {
            "status": "ok",
            "span_hz": str(span_hz),
            "rbw_hz": str(rbw_hz),
            "detector": detector,
        }

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
        except (OSError, MeasurementError, ValueError) as e:
            logger.warning(f"Failed to fetch current power: {e}")

        try:
            response = await self._scpi.query("FETCh:GPRF:MEASurement1:POWer:AVERage?")
            parts = response.split(",")
            if len(parts) >= 2:
                result.average_dbm = _parse_float(parts[1], "average_power")
        except (OSError, MeasurementError, ValueError) as e:
            logger.warning(f"Failed to fetch average power: {e}")

        try:
            response = await self._scpi.query("FETCh:GPRF:MEASurement1:POWer:MAXimum?")
            parts = response.split(",")
            if len(parts) >= 2:
                result.maximum_dbm = _parse_float(parts[1], "maximum_power")
        except (OSError, MeasurementError, ValueError) as e:
            logger.warning(f"Failed to fetch maximum power: {e}")

        try:
            response = await self._scpi.query("FETCh:GPRF:MEASurement1:POWer:MINimum?")
            parts = response.split(",")
            if len(parts) >= 2:
                result.minimum_dbm = _parse_float(parts[1], "minimum_power")
        except (OSError, MeasurementError, ValueError) as e:
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
        await self._scpi.send(f"ROUTe:GPRF:MEASurement1:SCENario {scenario.value}")

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
        await self._scpi.send(f"CONFigure:LTE:SIGN1:RFSettings:CHANnel:DL {config.dl_earfcn}")
        await self._scpi.send(f"CONFigure:LTE:SIGN1:RFSettings:DL:LEVel {config.dl_level_dbm}")

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

    async def lte_configure_bearer(
        self,
        apn: str = "default",
        ip_version: str = "IPV4",
    ) -> None:
        """Configure default EPS bearer.

        Args:
            apn: Access Point Name
            ip_version: IP version (IPV4, IPV6, IPV4V6)
        """
        sanitize_scpi_param(apn)
        sanitize_scpi_param(ip_version)
        await self._scpi.send(f"CONFigure:LTE:SIGN1:CONNection:APName '{apn}'")
        await self._scpi.send(f"CONFigure:LTE:SIGN1:CONNection:IPVersion {ip_version}")

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

    async def lte_meas_configure(
        self,
        stat_count: int = 10,
        repetition: str = "SINGleshot",
    ) -> dict[str, str]:
        """Configure LTE multi-evaluation measurement.

        Args:
            stat_count: Number of subframes to measure (default 10)
            repetition: Measurement repetition mode (SINGleshot, CONTinuous)
        """
        await self._scpi.send(f"CONFigure:LTE:MEAS1:MEValuation:SCOunt {stat_count}")
        sanitize_scpi_param(repetition)
        await self._scpi.send(f"CONFigure:LTE:MEAS1:MEValuation:REPetition {repetition}")
        return {
            "status": "ok",
            "stat_count": str(stat_count),
            "repetition": repetition,
        }

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
            response = await self._scpi.query("FETCh:LTE:MEAS1:MEValuation:POWer:CURRent?")
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                result.current_dbm = _parse_float(parts[1], "lte_power")
            if len(parts) >= 3:
                result.average_dbm = _parse_float(parts[2], "lte_avg_power")
        except (OSError, MeasurementError, ValueError) as e:
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
            response = await self._scpi.query("FETCh:LTE:MEAS1:MEValuation:MODulation:CURRent?")
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                result.evm_rms_percent = _parse_float(parts[1], "evm_rms")
            if len(parts) >= 3:
                result.evm_peak_percent = _parse_float(parts[2], "evm_peak")
        except (OSError, MeasurementError, ValueError) as e:
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
            response = await self._scpi.query("FETCh:LTE:MEAS1:MEValuation:ACLR:CURRent?")
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
            if len(parts) >= 3:
                result.aclr_minus_db = _parse_float(parts[1], "aclr_minus")
                result.aclr_plus_db = _parse_float(parts[2], "aclr_plus")
            if len(parts) >= 5:
                result.aclr_minus2_db = _parse_float(parts[3], "aclr_minus2")
                result.aclr_plus2_db = _parse_float(parts[4], "aclr_plus2")
        except (OSError, MeasurementError, ValueError) as e:
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
            response = await self._scpi.query("FETCh:LTE:MEAS1:MEValuation:SEMask:CURRent?")
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                # SEM pass/fail is typically in the first result field
                result.passed = parts[1].strip() in ("0", "PASS")
            if len(parts) >= 3:
                result.margin_db = _parse_float(parts[2], "sem_margin")
        except (OSError, MeasurementError, ValueError) as e:
            logger.warning(f"Failed to fetch LTE SEM: {e}")
        return result

    async def lte_meas_fetch_frequency_error(self) -> dict[str, Any]:
        """
        Fetch LTE frequency error measurement.

        Returns:
            Dictionary with frequency error data
        """
        try:
            response = await self._scpi.query("FETCh:LTE:MEAS1:MEValuation:FERRor:CURRent?")
            parts = response.split(",")
            result: dict[str, Any] = {"reliability": parts[0].strip() if parts else ""}
            if len(parts) >= 2:
                result["frequency_error_hz"] = _parse_float(parts[1], "freq_error")
            return result
        except (OSError, MeasurementError, ValueError) as e:
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
    # LTE RX / Extended BLER (receiver sensitivity)
    #
    # SCPI here (RSEP/EBL/PSW short forms, SOURce cell control, RFSettings:PCC
    # channel form) is preserved from field-validated sensitivity scripts. The
    # SIGN1 instance is equivalent to the bare "SIGN" the scripts used.
    # =========================================================================

    async def lte_set_operating_band(self, band: int) -> None:
        """Set the LTE signaling operating band (e.g. band 7 -> OB7)."""
        await self._scpi.send(f"CONFigure:LTE:SIGN1:BAND OB{int(band)}")

    async def lte_set_rx_bandwidth(self, bandwidth: LTEBandwidth) -> None:
        """Set the PCC downlink cell bandwidth for RX testing."""
        await self._scpi.send(f"CONFigure:LTE:SIGN1:CELL:BANDwidth:PCC:DL {bandwidth.value}")

    async def lte_set_earfcn(self, earfcn: int, direction: str = "DL") -> None:
        """Set the PCC EARFCN for the given direction ('DL' or 'UL')."""
        d = direction.strip().upper()
        if d not in ("DL", "UL"):
            raise ValueError("direction must be 'DL' or 'UL'")
        await self._scpi.send(f"CONFigure:LTE:SIGN1:RFSettings:PCC:CHANnel:{d} {int(earfcn)}")

    async def lte_set_rsepre_level(self, level_dbm: float) -> None:
        """Set the downlink RS-EPRE reference level (dBm/15 kHz)."""
        self._safety.validate_dl_level(level_dbm)
        await self._scpi.send(f"CONFigure:LTE:SIGN1:DL:PCC:RSEP:LEV {level_dbm}")

    async def lte_ebl_set_subframes(self, subframes: int) -> None:
        """Set the number of measured subframes for Extended BLER."""
        await self._scpi.send(f"CONFigure:LTE:SIGN1:EBL:SFR {int(subframes)}")

    async def lte_ebl_configure(self, subframes: int = 100, single_shot: bool = True) -> None:
        """Configure the Extended BLER measurement (repetition + subframes)."""
        await self._scpi.send(f"CONFigure:LTE:SIGN1:EBL:REP {'SING' if single_shot else 'CONT'}")
        await self.lte_ebl_set_subframes(subframes)

    async def lte_ebl_init(self) -> None:
        """Start a single Extended BLER measurement."""
        await self._scpi.send("INITiate:LTE:SIGN1:EBL")

    async def lte_ebl_fetch(self) -> EblResult:
        """Fetch the intermediate Extended BLER result for the PCC.

        Response layout (validated): ``reliability, ..., ..., BLER%, ...``.
        Reliability 19 means the call dropped / UE not attached.
        """
        raw = await self._scpi.query("FETCh:INT:LTE:SIGN1:EBL:PCC:REL?")
        parts = [p.strip() for p in raw.split(",")]
        result = EblResult(raw=raw.strip())
        if parts:
            result.reliability = parts[0]
        if result.dropped:
            return result
        if len(parts) > 3:
            try:
                result.bler_percent = float(parts[3])
            except ValueError:
                logger.debug(f"Unparseable EBL BLER field: {raw.strip()!r}")
        return result

    async def lte_sig_set_cell_state(self, on: bool) -> None:
        """Switch the LTE signaling cell ON/OFF (SOURce form used for RX flows)."""
        await self._scpi.send(f"SOURce:LTE:SIGN1:CELL:STAT {'ON' if on else 'OFF'}")
        self._cell_on = on

    async def lte_sig_cell_state_all(self) -> str:
        """Query combined cell state, e.g. 'ON,ADJ' when stable."""
        return await self._scpi.query("SOURce:LTE:SIGN1:CELL:STAT:ALL?")

    async def lte_ps_state(self) -> str:
        """Query the packet-switched connection state, e.g. 'ATT' when attached."""
        return await self._scpi.query("FETCh:LTE:SIGN1:PSW:STAT?")

    # =========================================================================
    # WLAN Non-Signaling
    # =========================================================================

    async def wlan_set_route(self, scenario: str = "SALone", meas_instance: int = 1) -> None:
        """Set WLAN measurement signal path scenario.

        Args:
            scenario: Signal path scenario string
            meas_instance: Measurement instance number (1-based)
        """
        await self._scpi.send(f"ROUTe:WLAN:MEAS{meas_instance}:SCENario {scenario}")

    async def wlan_set_standard(self, standard: str, meas_instance: int = 1) -> None:
        """Set WLAN standard.

        Args:
            standard: WLAN standard (A, B, G, N, AC, AX)
            meas_instance: Measurement instance number
        """
        await self._scpi.send(f"CONFigure:WLAN:MEAS{meas_instance}:MEValuation:STANdard {standard}")

    async def wlan_set_bandwidth(self, bandwidth: str, meas_instance: int = 1) -> None:
        """Set WLAN channel bandwidth.

        Args:
            bandwidth: Bandwidth string (BW20, BW40, BW80, BW160)
            meas_instance: Measurement instance number
        """
        await self._scpi.send(f"CONFigure:WLAN:MEAS{meas_instance}:MEValuation:BWIDth {bandwidth}")

    async def wlan_set_frequency(self, frequency_hz: float, meas_instance: int = 1) -> None:
        """Set WLAN measurement frequency.

        Args:
            frequency_hz: Frequency in Hz
            meas_instance: Measurement instance number
        """
        self._safety.validate_frequency(frequency_hz)
        await self._scpi.send(
            f"CONFigure:WLAN:MEAS{meas_instance}:RFSettings:FREQuency {frequency_hz}"
        )

    async def wlan_set_expected_power(self, power_dbm: float, meas_instance: int = 1) -> None:
        """Set WLAN expected input power.

        Args:
            power_dbm: Expected power in dBm
            meas_instance: Measurement instance number
        """
        self._safety.validate_expected_power(power_dbm)
        await self._scpi.send(f"CONFigure:WLAN:MEAS{meas_instance}:RFSettings:ENPower {power_dbm}")

    async def wlan_configure(self, config: Any) -> None:
        """Configure WLAN measurement from WLANMeasConfig.

        Args:
            config: WLANMeasConfig instance
        """
        n = config.meas_instance
        await self.wlan_set_route("SALone", n)
        await self.wlan_set_standard(config.standard.value, n)
        await self.wlan_set_bandwidth(config.bandwidth.value, n)
        await self.wlan_set_frequency(config.frequency_hz, n)
        await self.wlan_set_expected_power(config.expected_power_dbm, n)

    async def wlan_trigger(self, meas_instance: int = 1) -> None:
        """Trigger WLAN multi-evaluation measurement.

        Args:
            meas_instance: Measurement instance number
        """
        await self._scpi.send(f"INITiate:WLAN:MEAS{meas_instance}:MEValuation")

    async def wlan_fetch_power(self, meas_instance: int = 1) -> dict[str, Any]:
        """Fetch WLAN power measurement results.

        Args:
            meas_instance: Measurement instance number

        Returns:
            Dictionary with power measurement data
        """
        from ..models.cmw_types import WLANPowerResult

        result = WLANPowerResult()
        try:
            response = await self._scpi.query(
                f"FETCh:WLAN:MEAS{meas_instance}:MEValuation:POWer:CURRent?"
            )
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                result.power_dbm = _parse_float(parts[1], "wlan_power")
            if len(parts) >= 3:
                result.peak_power_dbm = _parse_float(parts[2], "wlan_peak_power")
        except (OSError, MeasurementError, ValueError) as e:
            logger.warning(f"Failed to fetch WLAN power: {e}")
        return result.to_dict()

    async def wlan_fetch_evm(self, meas_instance: int = 1) -> dict[str, Any]:
        """Fetch WLAN EVM measurement results.

        Args:
            meas_instance: Measurement instance number

        Returns:
            Dictionary with EVM measurement data
        """
        from ..models.cmw_types import WLANEVMResult

        result = WLANEVMResult()
        try:
            response = await self._scpi.query(
                f"FETCh:WLAN:MEAS{meas_instance}:MEValuation:MODulation:CURRent?"
            )
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                result.evm_all_carriers_db = _parse_float(parts[1], "wlan_evm_all")
            if len(parts) >= 3:
                result.evm_data_carriers_db = _parse_float(parts[2], "wlan_evm_data")
            if len(parts) >= 4:
                result.evm_pilot_carriers_db = _parse_float(parts[3], "wlan_evm_pilot")
        except (OSError, MeasurementError, ValueError) as e:
            logger.warning(f"Failed to fetch WLAN EVM: {e}")
        return result.to_dict()

    async def wlan_fetch_spectrum_flatness(self, meas_instance: int = 1) -> dict[str, Any]:
        """Fetch WLAN spectrum flatness measurement results.

        Args:
            meas_instance: Measurement instance number

        Returns:
            Dictionary with spectrum flatness data
        """
        from ..models.cmw_types import WLANSpectrumFlatnessResult

        result = WLANSpectrumFlatnessResult()
        try:
            response = await self._scpi.query(
                f"FETCh:WLAN:MEAS{meas_instance}:MEValuation:SFLatness:CURRent?"
            )
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                result.passed = parts[1].strip() in ("0", "PASS")
            if len(parts) >= 3:
                result.margin_db = _parse_float(parts[2], "wlan_sf_margin")
        except (OSError, MeasurementError, ValueError) as e:
            logger.warning(f"Failed to fetch WLAN spectrum flatness: {e}")
        return result.to_dict()

    async def wlan_fetch_frequency_error(self, meas_instance: int = 1) -> dict[str, Any]:
        """Fetch WLAN frequency error measurement results.

        Args:
            meas_instance: Measurement instance number

        Returns:
            Dictionary with frequency error data
        """
        try:
            response = await self._scpi.query(
                f"FETCh:WLAN:MEAS{meas_instance}:MEValuation:FERRor:CURRent?"
            )
            parts = response.split(",")
            result: dict[str, Any] = {"reliability": parts[0].strip() if parts else ""}
            if len(parts) >= 2:
                result["frequency_error_hz"] = _parse_float(parts[1], "wlan_freq_error")
            return result
        except (OSError, MeasurementError, ValueError) as e:
            logger.warning(f"Failed to fetch WLAN frequency error: {e}")
            return {"error": str(e)}

    async def wlan_fetch_all(self, meas_instance: int = 1) -> dict[str, Any]:
        """Fetch all WLAN measurement results.

        Args:
            meas_instance: Measurement instance number

        Returns:
            Dictionary with all WLAN measurement results
        """
        power = await self.wlan_fetch_power(meas_instance)
        evm = await self.wlan_fetch_evm(meas_instance)
        spectrum_flatness = await self.wlan_fetch_spectrum_flatness(meas_instance)
        frequency_error = await self.wlan_fetch_frequency_error(meas_instance)

        return {
            "power": power,
            "evm": evm,
            "spectrum_flatness": spectrum_flatness,
            "frequency_error": frequency_error,
        }

    # =========================================================================
    # Bluetooth / BLE Non-Signaling
    # =========================================================================

    async def bt_set_route(self, scenario: str = "SALone", meas_instance: int = 1) -> None:
        """Set Bluetooth measurement signal path scenario.

        Args:
            scenario: Signal path scenario string
            meas_instance: Measurement instance number
        """
        await self._scpi.send(f"ROUTe:BLUetooth:MEAS{meas_instance}:SCENario {scenario}")

    async def bt_set_technology(self, technology: str, meas_instance: int = 1) -> None:
        """Set Bluetooth technology (Classic or LE).

        Args:
            technology: Technology string (CLASsic or LENergy)
            meas_instance: Measurement instance number
        """
        await self._scpi.send(
            f"CONFigure:BLUetooth:MEAS{meas_instance}:MEValuation:TECHnology {technology}"
        )

    async def bt_set_ble_mode(self, mode: str, meas_instance: int = 1) -> None:
        """Set BLE PHY mode.

        Args:
            mode: BLE PHY mode (LE1M, LE2M, LECS2, LECS8)
            meas_instance: Measurement instance number
        """
        await self._scpi.send(
            f"CONFigure:BLUetooth:MEAS{meas_instance}:MEValuation:BURSt:TYPE {mode}"
        )

    async def bt_set_packet_type(self, packet_type: str, meas_instance: int = 1) -> None:
        """Set Bluetooth Classic packet type.

        Args:
            packet_type: Packet type string (DH1, DH3, etc.)
            meas_instance: Measurement instance number
        """
        await self._scpi.send(
            f"CONFigure:BLUetooth:MEAS{meas_instance}:MEValuation:PACKet:TYPE {packet_type}"
        )

    async def bt_set_frequency(self, frequency_hz: float, meas_instance: int = 1) -> None:
        """Set Bluetooth measurement frequency.

        Args:
            frequency_hz: Frequency in Hz
            meas_instance: Measurement instance number
        """
        self._safety.validate_frequency(frequency_hz)
        await self._scpi.send(
            f"CONFigure:BLUetooth:MEAS{meas_instance}:RFSettings:FREQuency {frequency_hz}"
        )

    async def bt_set_expected_power(self, power_dbm: float, meas_instance: int = 1) -> None:
        """Set Bluetooth expected input power.

        Args:
            power_dbm: Expected power in dBm
            meas_instance: Measurement instance number
        """
        self._safety.validate_expected_power(power_dbm)
        await self._scpi.send(
            f"CONFigure:BLUetooth:MEAS{meas_instance}:RFSettings:ENPower {power_dbm}"
        )

    async def bt_configure(self, config: Any) -> None:
        """Configure Bluetooth measurement from BTMeasConfig.

        Args:
            config: BTMeasConfig instance
        """
        n = config.meas_instance
        await self.bt_set_route("SALone", n)
        await self.bt_set_technology(config.technology.value, n)
        if config.technology.value == "LENergy":
            await self.bt_set_ble_mode(config.ble_mode.value, n)
        else:
            await self.bt_set_packet_type(config.packet_type.value, n)
        await self.bt_set_frequency(config.frequency_hz, n)
        await self.bt_set_expected_power(config.expected_power_dbm, n)

    async def bt_trigger(self, meas_instance: int = 1) -> None:
        """Trigger Bluetooth multi-evaluation measurement.

        Args:
            meas_instance: Measurement instance number
        """
        await self._scpi.send(f"INITiate:BLUetooth:MEAS{meas_instance}:MEValuation")

    async def bt_fetch_power(self, meas_instance: int = 1) -> dict[str, Any]:
        """Fetch Bluetooth power measurement results.

        Args:
            meas_instance: Measurement instance number

        Returns:
            Dictionary with power measurement data
        """
        from ..models.cmw_types import BTPowerResult

        result = BTPowerResult()
        try:
            response = await self._scpi.query(
                f"FETCh:BLUetooth:MEAS{meas_instance}:MEValuation:POWer:CURRent?"
            )
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                result.power_dbm = _parse_float(parts[1], "bt_power")
            if len(parts) >= 3:
                result.peak_power_dbm = _parse_float(parts[2], "bt_peak_power")
            if len(parts) >= 4:
                result.power_density_dbm_hz = _parse_float(parts[3], "bt_power_density")
        except (OSError, MeasurementError, ValueError) as e:
            logger.warning(f"Failed to fetch BT power: {e}")
        return result.to_dict()

    async def bt_fetch_modulation(self, meas_instance: int = 1) -> dict[str, Any]:
        """Fetch Bluetooth modulation (DEVM) measurement results.

        Args:
            meas_instance: Measurement instance number

        Returns:
            Dictionary with modulation measurement data
        """
        from ..models.cmw_types import BTModulationResult

        result = BTModulationResult()
        try:
            response = await self._scpi.query(
                f"FETCh:BLUetooth:MEAS{meas_instance}:MEValuation:MODulation:CURRent?"
            )
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                result.devm_rms_percent = _parse_float(parts[1], "bt_devm_rms")
            if len(parts) >= 3:
                result.devm_peak_percent = _parse_float(parts[2], "bt_devm_peak")
            if len(parts) >= 4:
                result.devm_99_percent = _parse_float(parts[3], "bt_devm_99")
        except (OSError, MeasurementError, ValueError) as e:
            logger.warning(f"Failed to fetch BT modulation: {e}")
        return result.to_dict()

    async def bt_fetch_frequency(self, meas_instance: int = 1) -> dict[str, Any]:
        """Fetch Bluetooth frequency measurement results.

        Args:
            meas_instance: Measurement instance number

        Returns:
            Dictionary with frequency measurement data
        """
        from ..models.cmw_types import BTFrequencyResult

        result = BTFrequencyResult()
        try:
            response = await self._scpi.query(
                f"FETCh:BLUetooth:MEAS{meas_instance}:MEValuation:FREQuency:CURRent?"
            )
            parts = response.split(",")
            if len(parts) >= 2:
                result.reliability = parts[0].strip()
                result.initial_offset_khz = _parse_float(parts[1], "bt_freq_offset")
            if len(parts) >= 3:
                result.carrier_drift_khz = _parse_float(parts[2], "bt_carrier_drift")
            if len(parts) >= 4:
                result.carrier_drift_rate_khz_us = _parse_float(parts[3], "bt_drift_rate")
        except (OSError, MeasurementError, ValueError) as e:
            logger.warning(f"Failed to fetch BT frequency: {e}")
        return result.to_dict()

    async def bt_fetch_all(self, meas_instance: int = 1) -> dict[str, Any]:
        """Fetch all Bluetooth measurement results.

        Args:
            meas_instance: Measurement instance number

        Returns:
            Dictionary with all Bluetooth measurement results
        """
        power = await self.bt_fetch_power(meas_instance)
        modulation = await self.bt_fetch_modulation(meas_instance)
        frequency = await self.bt_fetch_frequency(meas_instance)

        return {
            "power": power,
            "modulation": modulation,
            "frequency": frequency,
        }

    # =========================================================================
    # Bluetooth / BLE Signaling (receiver PER)
    #
    # Distinct from the non-signaling BLUetooth:MEAS measurement block above:
    # this drives the BLUetooth:SIGN signaling application (CMW as Central) to
    # measure DUT receiver PER. SCPI short forms preserved from validated scripts.
    # =========================================================================

    async def ble_sig_clear(self) -> None:
        """Clear the status/error queue (*CLS) before (re)configuring BLE."""
        await self._scpi.send("*CLS")

    async def ble_sig_set_packets(self, packets: int) -> None:
        """Set the number of packets per LE 1M PER measurement."""
        await self._scpi.send(f"CONFigure:BLUetooth:SIGN1:RXQ:PACK:NMOD:LEN:LE1M {int(packets)}")

    async def ble_sig_set_channel(self, channel: int) -> None:
        """Set the BLE measurement (data) channel index."""
        await self._scpi.send(f"CONFigure:BLUetooth:SIGN1:RFS:NMOD:MCH:LEN {int(channel)}")

    async def ble_sig_set_level(self, level_dbm: float) -> None:
        """Set the CMW BLE transmit level toward the DUT (dBm)."""
        self._safety.validate_generator_power(level_dbm)
        await self._scpi.send(f"CONFigure:BLUetooth:SIGN1:RFS:LEV {level_dbm}")

    async def ble_sig_read_per(self) -> PerResult:
        """Read the LE 1M PER result (reliability 0 = valid; index 1 = PER%)."""
        raw = await self._scpi.query("READ:BLUetooth:SIGN1:RXQ:PER:NMOD:LEN:LE1M?")
        parts = [p.strip() for p in raw.split(",")]
        result = PerResult(raw=raw.strip())
        if parts:
            result.reliability = parts[0]
        if result.reliability == "0" and len(parts) >= 2:
            try:
                result.per_percent = float(parts[1])
            except ValueError:
                logger.debug(f"Unparseable BLE PER field: {raw.strip()!r}")
        return result

    async def ble_sig_connection(self, action: str) -> None:
        """Drive the BLE LE connection action ('CONN' to connect, 'DET' to detach)."""
        act = action.strip().upper()
        if act not in ("CONN", "DET"):
            raise ValueError("action must be 'CONN' or 'DET'")
        await self._scpi.send(f"CALL:BLUetooth:SIGN1:CONN:ACT:LES {act}")

    # =========================================================================
    # WLAN Signaling (Access-Point emulation, for LTE+Wi-Fi coex)
    #
    # NOTE: these SCPI commands are derived from R&S application notes
    # (1C106 / 1C107), NOT from the field-validated coex scripts, and require the
    # WLAN (advanced) signaling license. Validate on hardware before relying on
    # them. String parameters are sanitized.
    # =========================================================================

    async def wlan_sig_set_route(self, scenario: str = "SAL") -> None:
        """Set the WLAN signaling routing scenario."""
        sanitize_scpi_param(scenario)
        await self._scpi.send(f"ROUTe:WLAN:SIGN1:SCENario {scenario}")

    async def wlan_sig_set_standard(self, standard: str) -> None:
        """Set the WLAN signaling standard (CMW token, e.g. GOFDm/HTOFdm/VHTofdm/HEOFdm)."""
        sanitize_scpi_param(standard)
        await self._scpi.send(f"CONFigure:WLAN:SIGN1:STANdard {standard}")

    async def wlan_sig_set_bandwidth(self, bandwidth: str) -> None:
        """Set the WLAN signaling bandwidth (BW20/BW40/BW80/BW160)."""
        sanitize_scpi_param(bandwidth)
        await self._scpi.send(f"CONFigure:WLAN:SIGN1:RFSettings:BWIDth {bandwidth}")

    async def wlan_sig_set_channel(self, channel: int) -> None:
        """Set the WLAN signaling operating channel number."""
        await self._scpi.send(f"CONFigure:WLAN:SIGN1:RFSettings:CHANnel {int(channel)}")

    async def wlan_sig_set_frequency(self, frequency_hz: float) -> None:
        """Set the WLAN signaling center frequency in Hz."""
        self._safety.validate_frequency(frequency_hz)
        await self._scpi.send(f"CONFigure:WLAN:SIGN1:RFSettings:FREQuency {frequency_hz}")

    async def wlan_sig_set_level(self, level_dbm: float) -> None:
        """Set the emulated AP transmit level in dBm."""
        self._safety.validate_generator_power(level_dbm)
        await self._scpi.send(f"CONFigure:WLAN:SIGN1:RFSettings:LEVel {level_dbm}")

    async def wlan_sig_set_ssid(self, ssid: str) -> None:
        """Set the emulated AP SSID."""
        sanitize_scpi_param(ssid)
        await self._scpi.send(f"CONFigure:WLAN:SIGN1:CONNection:SSID '{ssid}'")

    async def wlan_sig_set_security(self, security_type: str = "DISabled") -> None:
        """Set the emulated AP security type (DISabled/WPA/WPA2/WPA3 per license)."""
        sanitize_scpi_param(security_type)
        await self._scpi.send(f"CONFigure:WLAN:SIGN1:CONNection:STYPe {security_type}")

    async def wlan_sig_set_passphrase(self, passphrase: str) -> None:
        """Set the emulated AP WPA passphrase (test network only)."""
        sanitize_scpi_param(passphrase)
        await self._scpi.send(f"CONFigure:WLAN:SIGN1:CONNection:PASSphrase '{passphrase}'")

    async def wlan_sig_set_state(self, on: bool) -> None:
        """Switch the emulated AP ON/OFF."""
        await self._scpi.send(f"SOURce:WLAN:SIGN1:STATe {'ON' if on else 'OFF'}")

    async def wlan_sig_state_all(self) -> str:
        """Query combined AP state, e.g. 'ON,ADJ' when stable."""
        return await self._scpi.query("SOURce:WLAN:SIGN1:STATe:ALL?")

    async def wlan_sig_connection_state(self) -> str:
        """Query DUT association/connection state."""
        return await self._scpi.query("SENSe:WLAN:SIGN1:CONNection:STATe?")

    # =========================================================================
    # Enhanced GPRF
    # =========================================================================

    async def meas_set_trigger_source(self, source: str = "IF Power") -> None:
        """Set GPRF measurement trigger source.

        Args:
            source: Trigger source string
        """
        sanitize_scpi_param(source)
        await self._scpi.send(f"TRIGger:GPRF:MEAS1:POWer:SOURce '{source}'")

    async def meas_set_trigger_threshold(self, threshold_dbm: float) -> None:
        """Set GPRF measurement trigger threshold.

        Args:
            threshold_dbm: Trigger threshold in dBm
        """
        await self._scpi.send(f"TRIGger:GPRF:MEAS1:POWer:THReshold {threshold_dbm}")

    async def meas_set_power_filter(
        self, filter_type: str = "NONE", bandwidth_hz: float | None = None
    ) -> None:
        """Set GPRF power measurement filter.

        Args:
            filter_type: Filter type (NONE, GAUSs, etc.)
            bandwidth_hz: Filter bandwidth in Hz (if applicable)
        """
        sanitize_scpi_param(filter_type)
        await self._scpi.send(f"CONFigure:GPRF:MEAS1:POWer:FILTer:TYPE {filter_type}")
        if bandwidth_hz is not None:
            await self._scpi.send(f"CONFigure:GPRF:MEAS1:POWer:FILTer:BWIDth {bandwidth_hz}")

    async def gen_set_baseband_mode(self, mode: str = "CW") -> None:
        """Set generator baseband mode.

        Args:
            mode: Baseband mode (CW, ARB, etc.)
        """
        sanitize_scpi_param(mode)
        await self._scpi.send(f"SOURce:GPRF:GENerator1:BBMode {mode}")

    async def meas_set_user_margin(self, margin_db: float) -> None:
        """Set GPRF analyzer user margin.

        Args:
            margin_db: User margin in dB
        """
        await self._scpi.send(f"CONFigure:GPRF:MEAS1:RFSettings:UMARgin {margin_db}")

    async def gen_set_port(self, connector: str) -> None:
        """Set generator RF output port/connector.

        Args:
            connector: Connector/port string
        """
        sanitize_scpi_param(connector)
        await self._scpi.send(f"ROUTe:GPRF:GENerator1:SCENario:SPATh {connector}")

    async def meas_set_port(self, connector: str) -> None:
        """Set analyzer RF input port/connector.

        Args:
            connector: Connector/port string
        """
        sanitize_scpi_param(connector)
        await self._scpi.send(f"ROUTe:GPRF:MEAS1:SCENario:SPATh {connector}")

    async def system_all_off(self) -> None:
        """Turn off all generators and measurements (safe state)."""
        await self._scpi.send("SYSTem:GENerator:ALL:OFF")
        await self._scpi.send("SYSTem:MEASurement:ALL:OFF")
        self._generator_on = False

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
            except OSError as e:
                logger.warning(f"Failed to turn off generator during cleanup: {e}")
        await self.disconnect()

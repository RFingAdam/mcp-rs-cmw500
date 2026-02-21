"""CMW500 type definitions, enumerations, and data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CMW500Family(Enum):
    """
    CMW500 product variants.

    The CMW500 platform comes in different hardware configurations.
    """

    CMW500 = "CMW500"  # Full wideband tester
    CMW290 = "CMW290"  # Functional tester (subset)
    CMW270 = "CMW270"  # Wireless connectivity tester

    @property
    def supports_signaling(self) -> bool:
        """Whether this variant supports signaling mode."""
        return self in (CMW500Family.CMW500,)


class Technology(Enum):
    """Supported radio access technologies."""

    LTE_FDD = "LTE"
    LTE_TDD = "LTEA"
    WCDMA = "WCDMA"
    GSM = "GSM"
    WLAN = "WLAN"
    BLUETOOTH = "BT"
    GPRF = "GPRF"  # General Purpose RF


class MeasurementMode(Enum):
    """CMW500 measurement modes."""

    SIGNALING = "signaling"
    NON_SIGNALING = "non_signaling"


class LTEBandwidth(Enum):
    """LTE channel bandwidths."""

    BW1P4 = "B014"  # 1.4 MHz
    BW3 = "B030"  # 3 MHz
    BW5 = "B050"  # 5 MHz
    BW10 = "B100"  # 10 MHz
    BW15 = "B150"  # 15 MHz
    BW20 = "B200"  # 20 MHz

    @property
    def mhz(self) -> float:
        """Bandwidth in MHz."""
        bw_map = {
            "B014": 1.4,
            "B030": 3.0,
            "B050": 5.0,
            "B100": 10.0,
            "B150": 15.0,
            "B200": 20.0,
        }
        return bw_map[self.value]

    @classmethod
    def from_mhz(cls, mhz: float) -> "LTEBandwidth":
        """Create from MHz value."""
        mhz_map = {
            1.4: cls.BW1P4,
            3.0: cls.BW3,
            5.0: cls.BW5,
            10.0: cls.BW10,
            15.0: cls.BW15,
            20.0: cls.BW20,
        }
        if mhz not in mhz_map:
            raise ValueError(f"Invalid LTE bandwidth: {mhz} MHz. Must be one of {list(mhz_map)}")
        return mhz_map[mhz]


class SignalPath(Enum):
    """GPRF signal path scenarios."""

    STANDALONE = "SALone"  # Standalone analyzer
    CS_PATH = "CSPath"  # Combined signal path


class LTEDuplexMode(Enum):
    """LTE duplex modes."""

    FDD = "FDD"
    TDD = "TDD"


class ARBRepetition(Enum):
    """ARB waveform repetition modes."""

    CONTINUOUS = "CONTinuous"
    SINGLE = "SINGle"


class MeasRepetition(Enum):
    """Measurement repetition modes."""

    SINGLESHOT = "SINGleshot"
    CONTINUOUS = "CONTinuous"


@dataclass
class InstrumentInfo:
    """CMW500 identification information."""

    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    firmware_version: str = ""
    options: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serial_number": self.serial_number,
            "firmware_version": self.firmware_version,
            "options": self.options,
        }

    @classmethod
    def from_idn(cls, idn_string: str) -> "InstrumentInfo":
        """
        Parse *IDN? response into InstrumentInfo.

        Args:
            idn_string: Response from *IDN? command

        Returns:
            Parsed InstrumentInfo
        """
        parts = [p.strip() for p in idn_string.split(",")]
        return cls(
            manufacturer=parts[0] if len(parts) > 0 else "",
            model=parts[1] if len(parts) > 1 else "",
            serial_number=parts[2] if len(parts) > 2 else "",
            firmware_version=parts[3] if len(parts) > 3 else "",
        )


@dataclass
class PowerResult:
    """RF power measurement result."""

    current_dbm: float | None = None
    average_dbm: float | None = None
    maximum_dbm: float | None = None
    minimum_dbm: float | None = None
    reliability: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {}
        if self.current_dbm is not None:
            result["current_dbm"] = self.current_dbm
        if self.average_dbm is not None:
            result["average_dbm"] = self.average_dbm
        if self.maximum_dbm is not None:
            result["maximum_dbm"] = self.maximum_dbm
        if self.minimum_dbm is not None:
            result["minimum_dbm"] = self.minimum_dbm
        if self.reliability:
            result["reliability"] = self.reliability
        return result


@dataclass
class EVMResult:
    """EVM (Error Vector Magnitude) measurement result."""

    evm_rms_percent: float | None = None
    evm_peak_percent: float | None = None
    reliability: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {}
        if self.evm_rms_percent is not None:
            result["evm_rms_percent"] = self.evm_rms_percent
        if self.evm_peak_percent is not None:
            result["evm_peak_percent"] = self.evm_peak_percent
        if self.reliability:
            result["reliability"] = self.reliability
        return result


@dataclass
class ACLRResult:
    """ACLR (Adjacent Channel Leakage Ratio) measurement result."""

    aclr_minus_db: float | None = None  # Lower adjacent channel
    aclr_plus_db: float | None = None  # Upper adjacent channel
    aclr_minus2_db: float | None = None  # Lower alternate channel
    aclr_plus2_db: float | None = None  # Upper alternate channel
    reliability: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {}
        if self.aclr_minus_db is not None:
            result["aclr_minus_db"] = self.aclr_minus_db
        if self.aclr_plus_db is not None:
            result["aclr_plus_db"] = self.aclr_plus_db
        if self.aclr_minus2_db is not None:
            result["aclr_minus2_db"] = self.aclr_minus2_db
        if self.aclr_plus2_db is not None:
            result["aclr_plus2_db"] = self.aclr_plus2_db
        if self.reliability:
            result["reliability"] = self.reliability
        return result


@dataclass
class SEMResult:
    """SEM (Spectrum Emission Mask) measurement result."""

    passed: bool = False
    margin_db: float | None = None
    worst_offset_hz: float | None = None
    worst_margin_db: float | None = None
    reliability: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "passed": self.passed,
        }
        if self.margin_db is not None:
            result["margin_db"] = self.margin_db
        if self.worst_offset_hz is not None:
            result["worst_offset_hz"] = self.worst_offset_hz
        if self.worst_margin_db is not None:
            result["worst_margin_db"] = self.worst_margin_db
        if self.reliability:
            result["reliability"] = self.reliability
        return result


@dataclass
class BERResult:
    """BER (Bit Error Rate) measurement result."""

    ber: float | None = None
    total_bits: int = 0
    error_bits: int = 0
    reliability: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {}
        if self.ber is not None:
            result["ber"] = self.ber
        result["total_bits"] = self.total_bits
        result["error_bits"] = self.error_bits
        if self.reliability:
            result["reliability"] = self.reliability
        return result


@dataclass
class CellConfig:
    """LTE cell configuration."""

    band: int = 1
    bandwidth_mhz: float = 10.0
    dl_earfcn: int = 300
    dl_level_dbm: float = -60.0
    mcc: str = "001"
    mnc: str = "01"
    cdrx_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "band": self.band,
            "bandwidth_mhz": self.bandwidth_mhz,
            "dl_earfcn": self.dl_earfcn,
            "dl_level_dbm": self.dl_level_dbm,
            "mcc": self.mcc,
            "mnc": self.mnc,
            "cdrx_enabled": self.cdrx_enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CellConfig":
        """Create from dictionary."""
        return cls(
            band=data.get("band", 1),
            bandwidth_mhz=data.get("bandwidth_mhz", 10.0),
            dl_earfcn=data.get("dl_earfcn", 300),
            dl_level_dbm=data.get("dl_level_dbm", -60.0),
            mcc=data.get("mcc", "001"),
            mnc=data.get("mnc", "01"),
            cdrx_enabled=data.get("cdrx_enabled", False),
        )


@dataclass
class RFConfig:
    """RF configuration for GPRF generator/analyzer."""

    frequency_hz: float = 1e9
    level_dbm: float = -60.0
    external_attenuation_db: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "frequency_hz": self.frequency_hz,
            "level_dbm": self.level_dbm,
            "external_attenuation_db": self.external_attenuation_db,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RFConfig":
        """Create from dictionary."""
        return cls(
            frequency_hz=data.get("frequency_hz", 1e9),
            level_dbm=data.get("level_dbm", -60.0),
            external_attenuation_db=data.get("external_attenuation_db", 0.0),
        )

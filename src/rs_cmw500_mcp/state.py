"""Instrument state management for CMW500 configuration persistence."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class GeneratorState:
    """State of the GPRF generator."""

    frequency_hz: float | None = None
    level_dbm: float | None = None
    output_on: bool = False
    external_attenuation_db: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "frequency_hz": self.frequency_hz,
            "level_dbm": self.level_dbm,
            "output_on": self.output_on,
            "external_attenuation_db": self.external_attenuation_db,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeneratorState":
        """Create from dictionary."""
        return cls(
            frequency_hz=data.get("frequency_hz"),
            level_dbm=data.get("level_dbm"),
            output_on=data.get("output_on", False),
            external_attenuation_db=data.get("external_attenuation_db", 0.0),
        )


@dataclass
class AnalyzerState:
    """State of the GPRF analyzer."""

    frequency_hz: float | None = None
    expected_power_dbm: float | None = None
    external_attenuation_db: float = 0.0
    signal_path: str = "SALone"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "frequency_hz": self.frequency_hz,
            "expected_power_dbm": self.expected_power_dbm,
            "external_attenuation_db": self.external_attenuation_db,
            "signal_path": self.signal_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalyzerState":
        """Create from dictionary."""
        return cls(
            frequency_hz=data.get("frequency_hz"),
            expected_power_dbm=data.get("expected_power_dbm"),
            external_attenuation_db=data.get("external_attenuation_db", 0.0),
            signal_path=data.get("signal_path", "SALone"),
        )


@dataclass
class LTEState:
    """State of LTE signaling configuration."""

    cell_on: bool = False
    band: int = 1
    bandwidth_mhz: float = 10.0
    dl_earfcn: int = 300
    dl_level_dbm: float = -60.0
    connection_state: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cell_on": self.cell_on,
            "band": self.band,
            "bandwidth_mhz": self.bandwidth_mhz,
            "dl_earfcn": self.dl_earfcn,
            "dl_level_dbm": self.dl_level_dbm,
            "connection_state": self.connection_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LTEState":
        """Create from dictionary."""
        return cls(
            cell_on=data.get("cell_on", False),
            band=data.get("band", 1),
            bandwidth_mhz=data.get("bandwidth_mhz", 10.0),
            dl_earfcn=data.get("dl_earfcn", 300),
            dl_level_dbm=data.get("dl_level_dbm", -60.0),
            connection_state=data.get("connection_state", ""),
        )


@dataclass
class InstrumentState:
    """
    Complete CMW500 configuration state.

    Captures all relevant CMW500 settings that can be saved and restored,
    enabling reproducible measurements and configuration management.
    """

    generator: GeneratorState = field(default_factory=GeneratorState)
    analyzer: AnalyzerState = field(default_factory=AnalyzerState)
    lte: LTEState = field(default_factory=LTEState)
    timestamp: datetime = field(default_factory=datetime.now)
    instrument_info: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "generator": self.generator.to_dict(),
            "analyzer": self.analyzer.to_dict(),
            "lte": self.lte.to_dict(),
            "timestamp": self.timestamp.isoformat(),
            "instrument_info": self.instrument_info,
            "notes": self.notes,
            "version": "1.0",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstrumentState":
        """Create state from dictionary."""
        generator = GeneratorState.from_dict(data.get("generator", {}))
        analyzer = AnalyzerState.from_dict(data.get("analyzer", {}))
        lte = LTEState.from_dict(data.get("lte", {}))

        timestamp = datetime.now()
        if data.get("timestamp"):
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
            except ValueError:
                pass

        return cls(
            generator=generator,
            analyzer=analyzer,
            lte=lte,
            timestamp=timestamp,
            instrument_info=data.get("instrument_info", {}),
            notes=data.get("notes", ""),
        )

    def save(self, filepath: str | Path) -> None:
        """Save state to JSON file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str | Path) -> "InstrumentState":
        """Load state from JSON file."""
        filepath = Path(filepath)
        with open(filepath) as f:
            data = json.load(f)
        return cls.from_dict(data)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the state."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "generator": {
                "frequency_hz": self.generator.frequency_hz,
                "level_dbm": self.generator.level_dbm,
                "output_on": self.generator.output_on,
            },
            "analyzer": {
                "frequency_hz": self.analyzer.frequency_hz,
                "signal_path": self.analyzer.signal_path,
            },
            "lte": {
                "cell_on": self.lte.cell_on,
                "band": self.lte.band,
            },
            "instrument": self.instrument_info.get("model", "Unknown"),
        }


class StateManager:
    """
    Manages CMW500 state capture and restoration.

    Provides methods to capture current CMW500 state, save/load state files,
    and restore state to CMW500.
    """

    def __init__(self, state_directory: str | Path | None = None):
        """
        Initialize state manager.

        Args:
            state_directory: Directory for state files (default: ./cmw_states)
        """
        if state_directory is None:
            state_directory = Path("./cmw_states")
        self.state_directory = Path(state_directory)

    async def capture_state(self, cmw) -> InstrumentState:
        """
        Capture current CMW500 state.

        Args:
            cmw: CMW500Driver instance

        Returns:
            Captured InstrumentState
        """
        generator = GeneratorState(
            output_on=cmw._generator_on,
        )

        # Try to read current generator settings
        try:
            freq_resp = await cmw.scpi_query(
                "SOURce:GPRF:GENerator1:RFSettings:FREQuency?"
            )
            generator.frequency_hz = float(freq_resp)
        except Exception:
            pass

        try:
            level_resp = await cmw.scpi_query(
                "SOURce:GPRF:GENerator1:RFSettings:LEVel?"
            )
            generator.level_dbm = float(level_resp)
        except Exception:
            pass

        analyzer = AnalyzerState()
        try:
            freq_resp = await cmw.scpi_query(
                "CONFigure:GPRF:MEASurement1:RFSettings:FREQuency?"
            )
            analyzer.frequency_hz = float(freq_resp)
        except Exception:
            pass

        try:
            path_resp = await cmw.scpi_query("ROUTe:GPRF:MEASurement1:SCENario?")
            analyzer.signal_path = path_resp.strip()
        except Exception:
            pass

        lte = LTEState(cell_on=cmw._cell_on)
        try:
            conn_state = await cmw.lte_get_connection_state()
            lte.connection_state = conn_state.strip()
        except Exception:
            pass

        instrument_info = {}
        if cmw.info:
            instrument_info = cmw.info.to_dict()

        return InstrumentState(
            generator=generator,
            analyzer=analyzer,
            lte=lte,
            instrument_info=instrument_info,
        )

    async def restore_state(self, cmw, state: InstrumentState) -> None:
        """
        Restore CMW500 to saved state.

        Args:
            cmw: CMW500Driver instance
            state: State to restore
        """
        # Restore generator settings
        if state.generator.frequency_hz is not None:
            await cmw.gen_set_frequency(state.generator.frequency_hz)
        if state.generator.level_dbm is not None:
            await cmw.gen_set_level(state.generator.level_dbm)
        if state.generator.output_on:
            await cmw.gen_output_on()
        else:
            await cmw.gen_output_off()

        # Restore analyzer settings
        if state.analyzer.frequency_hz is not None:
            await cmw.meas_set_frequency(state.analyzer.frequency_hz)

        # Restore LTE settings
        if state.lte.cell_on:
            await cmw.lte_cell_on()

    def list_saved_states(self) -> list[dict[str, Any]]:
        """List all saved state files."""
        states = []
        if not self.state_directory.exists():
            return states

        for filepath in self.state_directory.glob("*.json"):
            try:
                state = InstrumentState.load(filepath)
                states.append({
                    "filename": filepath.name,
                    "path": str(filepath),
                    "summary": state.get_summary(),
                })
            except Exception as e:
                states.append({
                    "filename": filepath.name,
                    "path": str(filepath),
                    "error": str(e),
                })

        return states

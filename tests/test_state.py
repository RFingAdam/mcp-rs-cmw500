"""Tests for state management."""

import tempfile
from pathlib import Path

from rs_cmw500_mcp.state import (
    AnalyzerState,
    GeneratorState,
    InstrumentState,
    LTEState,
    StateManager,
)


class TestGeneratorState:
    """Test GeneratorState."""

    def test_defaults(self):
        state = GeneratorState()
        assert state.frequency_hz is None
        assert state.output_on is False

    def test_to_dict(self):
        state = GeneratorState(frequency_hz=1e9, level_dbm=-30.0, output_on=True)
        d = state.to_dict()
        assert d["frequency_hz"] == 1e9
        assert d["level_dbm"] == -30.0
        assert d["output_on"] is True

    def test_from_dict(self):
        state = GeneratorState.from_dict(
            {
                "frequency_hz": 2.4e9,
                "level_dbm": -20.0,
                "output_on": True,
            }
        )
        assert state.frequency_hz == 2.4e9
        assert state.output_on is True


class TestAnalyzerState:
    """Test AnalyzerState."""

    def test_defaults(self):
        state = AnalyzerState()
        assert state.signal_path == "SALone"

    def test_roundtrip(self):
        state = AnalyzerState(frequency_hz=1e9, expected_power_dbm=10.0)
        d = state.to_dict()
        restored = AnalyzerState.from_dict(d)
        assert restored.frequency_hz == state.frequency_hz


class TestLTEState:
    """Test LTEState."""

    def test_defaults(self):
        state = LTEState()
        assert state.cell_on is False
        assert state.band == 1

    def test_roundtrip(self):
        state = LTEState(cell_on=True, band=7, bandwidth_mhz=20.0)
        d = state.to_dict()
        restored = LTEState.from_dict(d)
        assert restored.cell_on is True
        assert restored.band == 7


class TestInstrumentState:
    """Test InstrumentState."""

    def test_defaults(self):
        state = InstrumentState()
        assert isinstance(state.generator, GeneratorState)
        assert isinstance(state.analyzer, AnalyzerState)
        assert isinstance(state.lte, LTEState)

    def test_to_dict(self):
        state = InstrumentState(
            generator=GeneratorState(frequency_hz=1e9, output_on=True),
            notes="test state",
        )
        d = state.to_dict()
        assert d["generator"]["frequency_hz"] == 1e9
        assert d["notes"] == "test state"
        assert "version" in d

    def test_from_dict(self):
        data = {
            "generator": {"frequency_hz": 1e9, "output_on": True},
            "analyzer": {"signal_path": "SALone"},
            "lte": {"cell_on": False},
            "notes": "test",
        }
        state = InstrumentState.from_dict(data)
        assert state.generator.frequency_hz == 1e9
        assert state.notes == "test"

    def test_save_and_load(self):
        """Test save/load roundtrip."""
        state = InstrumentState(
            generator=GeneratorState(frequency_hz=2.4e9, level_dbm=-30.0),
            notes="save test",
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            state.save(filepath)
            loaded = InstrumentState.load(filepath)
            assert loaded.generator.frequency_hz == 2.4e9
            assert loaded.notes == "save test"
        finally:
            Path(filepath).unlink(missing_ok=True)

    def test_get_summary(self):
        state = InstrumentState(
            generator=GeneratorState(frequency_hz=1e9, output_on=True),
        )
        summary = state.get_summary()
        assert "generator" in summary
        assert "timestamp" in summary


class TestStateManager:
    """Test StateManager."""

    def test_init_default_directory(self):
        manager = StateManager()
        assert manager.state_directory == Path("./cmw_states")

    def test_init_custom_directory(self):
        manager = StateManager("/tmp/test_states")
        assert manager.state_directory == Path("/tmp/test_states")

    def test_list_saved_states_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(tmpdir)
            states = manager.list_saved_states()
            assert states == []

    def test_list_saved_states(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(tmpdir)

            # Save a state
            state = InstrumentState(notes="list test")
            state.save(Path(tmpdir) / "test_state.json")

            states = manager.list_saved_states()
            assert len(states) == 1
            assert states[0]["filename"] == "test_state.json"

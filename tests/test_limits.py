"""Tests for limit management."""

import tempfile
from pathlib import Path

import pytest

from rs_cmw500_mcp.limits import (
    LimitLine,
    LimitManager,
    LimitSegment,
)


class TestLimitSegment:
    """Test LimitSegment."""

    def test_max_only(self):
        seg = LimitSegment(parameter="power_dbm", max_value=23.0, unit="dBm")
        assert seg.check_value(20.0) is None  # Pass
        failure = seg.check_value(25.0)
        assert failure is not None
        assert failure.limit_type == "max"

    def test_min_only(self):
        seg = LimitSegment(parameter="power_dbm", min_value=-50.0, unit="dBm")
        assert seg.check_value(-40.0) is None  # Pass
        failure = seg.check_value(-55.0)
        assert failure is not None
        assert failure.limit_type == "min"

    def test_both_limits(self):
        seg = LimitSegment(parameter="evm_percent", max_value=8.0, min_value=0.0, unit="%")
        assert seg.check_value(5.0) is None  # Pass
        assert seg.check_value(10.0) is not None  # Fail max
        assert seg.check_value(-1.0) is not None  # Fail min

    def test_no_limits_raises(self):
        with pytest.raises(ValueError):
            LimitSegment(parameter="test")

    def test_to_dict(self):
        seg = LimitSegment(parameter="power", max_value=23.0, unit="dBm")
        d = seg.to_dict()
        assert d["parameter"] == "power"
        assert d["max_value"] == 23.0

    def test_from_dict(self):
        seg = LimitSegment.from_dict(
            {
                "parameter": "evm",
                "max_value": 8.0,
                "unit": "%",
            }
        )
        assert seg.parameter == "evm"
        assert seg.max_value == 8.0


class TestLimitLine:
    """Test LimitLine."""

    def test_check_pass(self):
        limit = LimitLine(
            name="power_limit",
            segments=[
                LimitSegment(parameter="power_dbm", max_value=23.0, min_value=20.0),
            ],
        )
        result = limit.check({"power_dbm": 21.5})
        assert result.passed is True
        assert result.failed_checks == 0

    def test_check_fail(self):
        limit = LimitLine(
            name="power_limit",
            segments=[
                LimitSegment(parameter="power_dbm", max_value=23.0),
            ],
        )
        result = limit.check({"power_dbm": 25.0})
        assert result.passed is False
        assert result.failed_checks == 1

    def test_check_multiple_segments(self):
        limit = LimitLine(
            name="rf_limits",
            segments=[
                LimitSegment(parameter="power_dbm", max_value=23.0),
                LimitSegment(parameter="evm_percent", max_value=8.0),
            ],
        )
        result = limit.check({"power_dbm": 20.0, "evm_percent": 5.0})
        assert result.passed is True
        assert result.total_checks == 2

    def test_check_missing_parameter(self):
        limit = LimitLine(
            name="test",
            segments=[
                LimitSegment(parameter="missing_param", max_value=10.0),
            ],
        )
        result = limit.check({"power_dbm": 20.0})
        assert result.passed is True
        assert result.total_checks == 0

    def test_save_and_load(self):
        limit = LimitLine(
            name="test_limit",
            segments=[
                LimitSegment(parameter="power", max_value=23.0, unit="dBm"),
            ],
            description="Test limit",
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            limit.save(filepath)
            loaded = LimitLine.load(filepath)
            assert loaded.name == "test_limit"
            assert len(loaded.segments) == 1
            assert loaded.segments[0].max_value == 23.0
        finally:
            Path(filepath).unlink(missing_ok=True)


class TestLimitManager:
    """Test LimitManager."""

    def test_add_and_get(self):
        manager = LimitManager()
        limit = LimitLine(
            name="test",
            segments=[LimitSegment(parameter="power", max_value=23.0)],
        )
        manager.add_limit(limit)
        assert manager.get_limit("test") is not None

    def test_remove(self):
        manager = LimitManager()
        limit = LimitLine(
            name="test",
            segments=[LimitSegment(parameter="power", max_value=23.0)],
        )
        manager.add_limit(limit)
        assert manager.remove_limit("test") is True
        assert manager.remove_limit("test") is False

    def test_list(self):
        manager = LimitManager()
        manager.add_limit(
            LimitLine(
                name="a",
                segments=[LimitSegment(parameter="p", max_value=1.0)],
            )
        )
        manager.add_limit(
            LimitLine(
                name="b",
                segments=[LimitSegment(parameter="q", max_value=2.0)],
            )
        )
        names = manager.list_limits()
        assert "a" in names
        assert "b" in names

    def test_clear(self):
        manager = LimitManager()
        manager.add_limit(
            LimitLine(
                name="test",
                segments=[LimitSegment(parameter="p", max_value=1.0)],
            )
        )
        manager.clear_limits()
        assert manager.list_limits() == []

    def test_check_all(self):
        manager = LimitManager()
        manager.add_limit(
            LimitLine(
                name="power",
                segments=[LimitSegment(parameter="power_dbm", max_value=23.0)],
            )
        )
        manager.add_limit(
            LimitLine(
                name="evm",
                segments=[LimitSegment(parameter="evm_percent", max_value=8.0)],
            )
        )
        results = manager.check_all({"power_dbm": 20.0, "evm_percent": 5.0})
        assert results["power"].passed is True
        assert results["evm"].passed is True

    def test_get_overall_status(self):
        manager = LimitManager()
        manager.add_limit(
            LimitLine(
                name="power",
                segments=[LimitSegment(parameter="power_dbm", max_value=23.0)],
            )
        )
        status = manager.get_overall_status({"power_dbm": 25.0})
        assert status["overall_passed"] is False
        assert status["limits_failed"] == 1

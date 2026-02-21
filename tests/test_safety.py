"""Tests for safety validators."""

import pytest

from rs_cmw500_mcp.exceptions import SafetyError
from rs_cmw500_mcp.safety.validators import SafetyLimits, SafetyValidator


class TestSafetyLimits:
    """Test SafetyLimits dataclass."""

    def test_defaults(self):
        limits = SafetyLimits()
        assert limits.max_generator_power_dbm == 0.0
        assert limits.min_generator_power_dbm == -130.0
        assert limits.max_expected_power_dbm == 33.0
        assert limits.max_frequency_hz == 6e9
        assert limits.min_frequency_hz == 70e6

    def test_custom_limits(self):
        limits = SafetyLimits(
            max_generator_power_dbm=-10.0,
            min_generator_power_dbm=-100.0,
            max_frequency_hz=3e9,
        )
        assert limits.max_generator_power_dbm == -10.0
        assert limits.min_generator_power_dbm == -100.0
        assert limits.max_frequency_hz == 3e9


class TestSafetyValidator:
    """Test SafetyValidator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SafetyValidator()

    def test_valid_generator_power(self):
        """Valid power should not raise."""
        self.validator.validate_generator_power(-30.0)
        self.validator.validate_generator_power(0.0)
        self.validator.validate_generator_power(-130.0)

    def test_generator_power_too_high(self):
        """Power above max should raise SafetyError."""
        with pytest.raises(SafetyError) as exc_info:
            self.validator.validate_generator_power(10.0)
        assert exc_info.value.parameter == "generator_power_dbm"
        assert exc_info.value.value == 10.0

    def test_generator_power_too_low(self):
        """Power below min should raise SafetyError."""
        with pytest.raises(SafetyError):
            self.validator.validate_generator_power(-140.0)

    def test_valid_expected_power(self):
        """Valid expected power should not raise."""
        self.validator.validate_expected_power(0.0)
        self.validator.validate_expected_power(33.0)

    def test_expected_power_too_high(self):
        """Expected power above max should raise SafetyError."""
        with pytest.raises(SafetyError) as exc_info:
            self.validator.validate_expected_power(40.0)
        assert exc_info.value.parameter == "expected_power_dbm"

    def test_valid_frequency(self):
        """Valid frequency should not raise."""
        self.validator.validate_frequency(1e9)
        self.validator.validate_frequency(70e6)
        self.validator.validate_frequency(6e9)

    def test_frequency_too_high(self):
        """Frequency above max should raise SafetyError."""
        with pytest.raises(SafetyError) as exc_info:
            self.validator.validate_frequency(7e9)
        assert exc_info.value.parameter == "frequency_hz"

    def test_frequency_too_low(self):
        """Frequency below min should raise SafetyError."""
        with pytest.raises(SafetyError):
            self.validator.validate_frequency(1e6)

    def test_valid_dl_level(self):
        """Valid DL level should not raise."""
        self.validator.validate_dl_level(-60.0)
        self.validator.validate_dl_level(0.0)

    def test_dl_level_too_high(self):
        """DL level above max should raise SafetyError."""
        with pytest.raises(SafetyError):
            self.validator.validate_dl_level(10.0)

    def test_custom_limits(self):
        """Custom limits should be respected."""
        limits = SafetyLimits(max_generator_power_dbm=-20.0)
        validator = SafetyValidator(limits)
        with pytest.raises(SafetyError):
            validator.validate_generator_power(-10.0)

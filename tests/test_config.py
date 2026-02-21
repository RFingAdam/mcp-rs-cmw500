"""Tests for CMW500 configuration."""

import os
from unittest.mock import patch

from rs_cmw500_mcp.config import CMWSettings, get_settings, reload_settings
from rs_cmw500_mcp.safety.validators import SafetyLimits


class TestCMWSettings:
    """Test CMWSettings."""

    def test_defaults(self):
        """Test default settings."""
        settings = CMWSettings()
        assert settings.default_host == "127.0.0.1"
        assert settings.default_port == 5025
        assert settings.connection_timeout == 5.0
        assert settings.command_timeout == 30.0
        assert settings.max_generator_power_dbm == 0.0
        assert settings.min_generator_power_dbm == -130.0
        assert settings.max_expected_power_dbm == 33.0
        assert settings.max_frequency_hz == 6e9
        assert settings.min_frequency_hz == 70e6
        assert settings.log_level == "INFO"

    def test_get_safety_limits(self):
        """Test creating SafetyLimits from settings."""
        settings = CMWSettings()
        limits = settings.get_safety_limits()
        assert isinstance(limits, SafetyLimits)
        assert limits.max_generator_power_dbm == 0.0
        assert limits.max_frequency_hz == 6e9

    def test_env_prefix(self):
        """Test that CMW_ prefix is used."""
        with patch.dict(os.environ, {"CMW_DEFAULT_HOST": "10.0.0.1"}):
            settings = CMWSettings()
            assert settings.default_host == "10.0.0.1"

    def test_env_safety_limits(self):
        """Test safety limits from environment."""
        with patch.dict(os.environ, {"CMW_MAX_GENERATOR_POWER_DBM": "-10"}):
            settings = CMWSettings()
            assert settings.max_generator_power_dbm == -10.0


class TestGetSettings:
    """Test settings singleton."""

    def test_get_settings(self):
        """Test getting settings instance."""
        # Force reload to start fresh
        settings = reload_settings()
        assert isinstance(settings, CMWSettings)

    def test_singleton(self):
        """Test that get_settings returns same instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_reload(self):
        """Test reload creates new instance."""
        s1 = get_settings()
        s2 = reload_settings()
        assert s1 is not s2

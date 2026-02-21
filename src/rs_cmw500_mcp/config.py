"""Configuration management using Pydantic settings."""

import logging

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .safety.validators import SafetyLimits


class CMWSettings(BaseSettings):
    """
    CMW500 MCP server configuration.

    Settings can be configured via environment variables with CMW_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="CMW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Connection defaults
    default_host: str = Field(default="127.0.0.1", description="Default CMW500 host")
    default_port: int = Field(default=5025, description="Default CMW500 port")
    connection_timeout: float = Field(default=5.0, description="Connection timeout in seconds")
    command_timeout: float = Field(default=30.0, description="Command timeout in seconds")

    # Safety limits
    max_generator_power_dbm: float = Field(
        default=0.0, description="Maximum generator output power in dBm"
    )
    min_generator_power_dbm: float = Field(
        default=-130.0, description="Minimum generator power in dBm"
    )
    max_expected_power_dbm: float = Field(
        default=33.0, description="Maximum expected power for analyzer in dBm"
    )
    max_frequency_hz: float = Field(default=6e9, description="Maximum frequency in Hz")
    min_frequency_hz: float = Field(default=70e6, description="Minimum frequency in Hz")

    # Raw SCPI access
    allow_raw_scpi: bool = Field(
        default=True,
        description="Allow raw SCPI command execution (default: True for backwards compat)",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")

    def get_safety_limits(self) -> SafetyLimits:
        """Create SafetyLimits from settings."""
        return SafetyLimits(
            max_generator_power_dbm=self.max_generator_power_dbm,
            min_generator_power_dbm=self.min_generator_power_dbm,
            max_expected_power_dbm=self.max_expected_power_dbm,
            max_frequency_hz=self.max_frequency_hz,
            min_frequency_hz=self.min_frequency_hz,
        )

    def configure_logging(self) -> None:
        """Configure logging based on settings."""
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )


# Global settings instance
_settings: CMWSettings | None = None


def get_settings() -> CMWSettings:
    """Get or create settings instance."""
    global _settings
    if _settings is None:
        _settings = CMWSettings()
    return _settings


def reload_settings() -> CMWSettings:
    """Reload settings from environment."""
    global _settings
    _settings = CMWSettings()
    return _settings

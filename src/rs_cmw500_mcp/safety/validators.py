"""Safety validators for CMW500 parameters."""

import logging
from dataclasses import dataclass

from ..exceptions import SafetyError

logger = logging.getLogger(__name__)


@dataclass
class SafetyLimits:
    """
    Safety limits for CMW500 parameters.

    All limits are configurable via environment variables with CMW_ prefix.
    """

    max_generator_power_dbm: float = 0.0
    min_generator_power_dbm: float = -130.0
    max_expected_power_dbm: float = 33.0
    max_frequency_hz: float = 6e9  # 6 GHz
    min_frequency_hz: float = 70e6  # 70 MHz


class SafetyValidator:
    """
    Validates CMW500 parameters against safety limits.

    Prevents accidental damage to equipment or DUT by enforcing
    configurable limits on power, frequency, and other parameters.
    """

    def __init__(self, limits: SafetyLimits | None = None):
        """
        Initialize validator with limits.

        Args:
            limits: Safety limits (uses defaults if None)
        """
        self.limits = limits or SafetyLimits()

    def validate_generator_power(self, power_dbm: float) -> None:
        """
        Validate generator output power level.

        Args:
            power_dbm: Power level in dBm

        Raises:
            SafetyError: If power exceeds limits
        """
        if power_dbm > self.limits.max_generator_power_dbm:
            raise SafetyError(
                f"Generator power {power_dbm} dBm exceeds maximum allowed "
                f"{self.limits.max_generator_power_dbm} dBm",
                parameter="generator_power_dbm",
                value=power_dbm,
                limit=self.limits.max_generator_power_dbm,
            )

        if power_dbm < self.limits.min_generator_power_dbm:
            raise SafetyError(
                f"Generator power {power_dbm} dBm below minimum allowed "
                f"{self.limits.min_generator_power_dbm} dBm",
                parameter="generator_power_dbm",
                value=power_dbm,
                limit=self.limits.min_generator_power_dbm,
            )

        logger.debug(f"Generator power {power_dbm} dBm validated")

    def validate_expected_power(self, power_dbm: float) -> None:
        """
        Validate expected input power for analyzer.

        Args:
            power_dbm: Expected power level in dBm

        Raises:
            SafetyError: If power exceeds limits
        """
        if power_dbm > self.limits.max_expected_power_dbm:
            raise SafetyError(
                f"Expected power {power_dbm} dBm exceeds maximum allowed "
                f"{self.limits.max_expected_power_dbm} dBm",
                parameter="expected_power_dbm",
                value=power_dbm,
                limit=self.limits.max_expected_power_dbm,
            )

        logger.debug(f"Expected power {power_dbm} dBm validated")

    def validate_frequency(self, frequency_hz: float) -> None:
        """
        Validate frequency.

        Args:
            frequency_hz: Frequency in Hz

        Raises:
            SafetyError: If frequency exceeds limits
        """
        if frequency_hz > self.limits.max_frequency_hz:
            raise SafetyError(
                f"Frequency {frequency_hz/1e9:.3f} GHz exceeds maximum "
                f"{self.limits.max_frequency_hz/1e9:.3f} GHz",
                parameter="frequency_hz",
                value=frequency_hz,
                limit=self.limits.max_frequency_hz,
            )

        if frequency_hz < self.limits.min_frequency_hz:
            raise SafetyError(
                f"Frequency {frequency_hz/1e6:.3f} MHz below minimum "
                f"{self.limits.min_frequency_hz/1e6:.3f} MHz",
                parameter="frequency_hz",
                value=frequency_hz,
                limit=self.limits.min_frequency_hz,
            )

        logger.debug(f"Frequency {frequency_hz/1e6:.3f} MHz validated")

    def validate_dl_level(self, level_dbm: float) -> None:
        """
        Validate downlink signal level for signaling mode.

        Uses the same limits as generator power.

        Args:
            level_dbm: Downlink level in dBm

        Raises:
            SafetyError: If level exceeds limits
        """
        if level_dbm > self.limits.max_generator_power_dbm:
            raise SafetyError(
                f"DL level {level_dbm} dBm exceeds maximum allowed "
                f"{self.limits.max_generator_power_dbm} dBm",
                parameter="dl_level_dbm",
                value=level_dbm,
                limit=self.limits.max_generator_power_dbm,
            )

        logger.debug(f"DL level {level_dbm} dBm validated")

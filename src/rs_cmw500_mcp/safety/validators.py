"""Safety validators for CMW500 parameters."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from ..exceptions import SafetyError

logger = logging.getLogger(__name__)


# SCPI metacharacters that could be used for command injection
_SCPI_DANGEROUS_CHARS = re.compile(r"[;\n\r]")


def sanitize_scpi_param(value: str) -> str:
    """
    Sanitize a user-provided string parameter before interpolation into SCPI commands.

    Rejects strings containing SCPI metacharacters that could enable command injection:
    - `;` (SCPI command separator - could chain arbitrary commands)
    - `\\n` and `\\r` (newlines - could inject commands on new lines)
    - Leading `*` (could trigger instrument commands like *RST, *CLS, *OPC)

    Numeric/float parameters validated by SafetyValidator do not need this check.
    This is for string parameters like filenames, identifiers, MCC/MNC codes, etc.

    Args:
        value: User-provided string parameter

    Returns:
        The original string if it passes validation

    Raises:
        ValueError: If the string contains dangerous SCPI metacharacters
    """
    if not isinstance(value, str):
        raise ValueError(f"Expected string parameter, got {type(value).__name__}")

    if _SCPI_DANGEROUS_CHARS.search(value):
        raise ValueError(
            f"SCPI parameter contains prohibited characters (semicolons, newlines): {value!r}"
        )

    if value.lstrip().startswith("*"):
        raise ValueError(
            f"SCPI parameter must not start with '*' (could trigger instrument commands): {value!r}"
        )

    return value


def validate_safe_path(user_path: str | Path, base_dir: str | Path) -> Path:
    """
    Validate that a user-provided path resolves safely within the base directory.

    Guards against directory traversal attacks (../) , absolute path escapes,
    and symlinks pointing outside the allowed base directory.

    Args:
        user_path: User-provided file path or filename
        base_dir: Base directory that the resolved path must stay within

    Returns:
        The resolved, validated Path

    Raises:
        ValueError: If the path escapes the base directory or is otherwise unsafe
    """
    base = Path(base_dir).resolve()
    resolved = (base / Path(user_path)).resolve()

    # Check that resolved path is within base directory
    if not resolved.is_relative_to(base):
        raise ValueError(
            f"Path traversal detected: resolved path {resolved} is not within base directory {base}"
        )

    # Check for symlinks that point outside base_dir
    # Walk up the path checking each component that exists
    check_path = resolved
    while check_path != base and check_path != check_path.parent:
        if check_path.is_symlink():
            link_target = check_path.resolve()
            if not link_target.is_relative_to(base):
                raise ValueError(
                    f"Symlink escape detected: {check_path} points to "
                    f"{link_target} which is outside {base}"
                )
        check_path = check_path.parent

    return resolved


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
                f"Frequency {frequency_hz / 1e9:.3f} GHz exceeds maximum "
                f"{self.limits.max_frequency_hz / 1e9:.3f} GHz",
                parameter="frequency_hz",
                value=frequency_hz,
                limit=self.limits.max_frequency_hz,
            )

        if frequency_hz < self.limits.min_frequency_hz:
            raise SafetyError(
                f"Frequency {frequency_hz / 1e6:.3f} MHz below minimum "
                f"{self.limits.min_frequency_hz / 1e6:.3f} MHz",
                parameter="frequency_hz",
                value=frequency_hz,
                limit=self.limits.min_frequency_hz,
            )

        logger.debug(f"Frequency {frequency_hz / 1e6:.3f} MHz validated")

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

        if level_dbm < self.limits.min_generator_power_dbm:
            raise SafetyError(
                f"DL level {level_dbm} dBm below minimum {self.limits.min_generator_power_dbm} dBm",
                parameter="dl_level_dbm",
                value=level_dbm,
                limit=self.limits.min_generator_power_dbm,
            )

        logger.debug(f"DL level {level_dbm} dBm validated")

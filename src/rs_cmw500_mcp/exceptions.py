"""Custom exceptions for CMW500 operations.

This module defines all exceptions at the package root level to avoid
circular import issues between driver and safety modules.
"""


class CMW500Error(Exception):
    """Base exception for CMW500 errors."""

    def __init__(self, message: str, address: str | None = None):
        self.message = message
        self.address = address
        super().__init__(f"{message}" + (f" (address: {address})" if address else ""))


class ConnectionError(CMW500Error):
    """Error connecting to CMW500."""

    pass


class CommunicationError(CMW500Error):
    """Error communicating with CMW500."""

    pass


class ConfigurationError(CMW500Error):
    """Error configuring CMW500 settings."""

    pass


class MeasurementError(CMW500Error):
    """Error during measurement."""

    pass


class SafetyError(CMW500Error):
    """Safety limit violation."""

    def __init__(
        self,
        message: str,
        parameter: str,
        value: float,
        limit: float,
        address: str | None = None,
    ):
        self.parameter = parameter
        self.value = value
        self.limit = limit
        super().__init__(message, address)


class TimeoutError(CMW500Error):
    """Operation timed out."""

    pass


class SignalingError(CMW500Error):
    """Error in signaling operations (cell, connection, bearer)."""

    pass

"""Tests for CMW500 exception hierarchy."""


from rs_cmw500_mcp.exceptions import (
    CMW500Error,
    CommunicationError,
    ConfigurationError,
    ConnectionError,
    MeasurementError,
    SafetyError,
    SignalingError,
    TimeoutError,
)


class TestExceptionHierarchy:
    """Test that all exceptions inherit from CMW500Error."""

    def test_base_exception(self):
        err = CMW500Error("test error")
        assert str(err) == "test error"
        assert err.message == "test error"
        assert err.address is None

    def test_base_exception_with_address(self):
        err = CMW500Error("test error", address="192.168.1.100:5025")
        assert "192.168.1.100:5025" in str(err)
        assert err.address == "192.168.1.100:5025"

    def test_connection_error(self):
        err = ConnectionError("Connection refused")
        assert isinstance(err, CMW500Error)

    def test_communication_error(self):
        err = CommunicationError("Send failed")
        assert isinstance(err, CMW500Error)

    def test_configuration_error(self):
        err = ConfigurationError("Invalid config")
        assert isinstance(err, CMW500Error)

    def test_measurement_error(self):
        err = MeasurementError("Measurement failed")
        assert isinstance(err, CMW500Error)

    def test_safety_error(self):
        err = SafetyError(
            "Power too high",
            parameter="power_dbm",
            value=10.0,
            limit=0.0,
        )
        assert isinstance(err, CMW500Error)
        assert err.parameter == "power_dbm"
        assert err.value == 10.0
        assert err.limit == 0.0

    def test_timeout_error(self):
        err = TimeoutError("Timed out")
        assert isinstance(err, CMW500Error)

    def test_signaling_error(self):
        err = SignalingError("Cell setup failed")
        assert isinstance(err, CMW500Error)

"""Generic RF power measurement template."""

from dataclasses import dataclass

from .base import MeasurementTemplate


@dataclass
class GPRFPowerTemplate(MeasurementTemplate):
    """
    Template for generic GPRF power measurement.

    Configures CMW500 GPRF analyzer for power measurement at
    a specified frequency with configurable measurement parameters.
    """

    name: str = "GPRF Power Measurement"
    description: str = "Generic RF power measurement at specified frequency"
    technology: str = "GPRF"

    def __post_init__(self):
        """Set default parameters if not provided."""
        if not self.parameters:
            self.parameters = {
                "frequency_hz": 1e9,
                "expected_power_dbm": 0.0,
                "statistic_count": 10,
                "meas_length_s": 0.001,
                "signal_path": "SALone",
            }

    @classmethod
    def create(
        cls,
        frequency_hz: float = 1e9,
        expected_power_dbm: float = 0.0,
        statistic_count: int = 10,
        meas_length_s: float = 0.001,
    ) -> "GPRFPowerTemplate":
        """
        Create a GPRF power measurement template.

        Args:
            frequency_hz: Measurement frequency in Hz
            expected_power_dbm: Expected input power in dBm
            statistic_count: Number of measurements for statistics
            meas_length_s: Measurement length in seconds

        Returns:
            Configured GPRFPowerTemplate
        """
        return cls(
            parameters={
                "frequency_hz": frequency_hz,
                "expected_power_dbm": expected_power_dbm,
                "statistic_count": statistic_count,
                "meas_length_s": meas_length_s,
                "signal_path": "SALone",
            }
        )

    async def apply(self, cmw) -> None:
        """
        Apply GPRF power measurement configuration to CMW500.

        Args:
            cmw: CMW500Driver instance
        """
        from ..models.cmw_types import SignalPath

        # Set signal path
        signal_path = self.parameters.get("signal_path", "SALone")
        if signal_path == "SALone":
            await cmw.set_signal_path(SignalPath.STANDALONE)
        else:
            await cmw.set_signal_path(SignalPath.CS_PATH)

        # Configure analyzer
        await cmw.meas_set_frequency(self.parameters["frequency_hz"])
        await cmw.meas_set_expected_power(self.parameters["expected_power_dbm"])
        await cmw.meas_configure_power(
            statistic_count=self.parameters.get("statistic_count", 10),
            meas_length_s=self.parameters.get("meas_length_s", 0.001),
        )

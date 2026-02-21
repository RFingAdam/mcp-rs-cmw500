"""Non-signaling RX sensitivity test template."""

from dataclasses import dataclass

from .base import MeasurementTemplate


@dataclass
class NonSignalingRxTemplate(MeasurementTemplate):
    """
    Template for non-signaling RX sensitivity/BER test.

    Configures CMW500 generator to output a modulated signal
    and analyzer to measure DUT response (e.g., via BER feedback).
    Uses both generator and analyzer subsystems.
    """

    name: str = "Non-Signaling RX Test"
    description: str = "BER/sensitivity test with generator + analyzer configuration"
    technology: str = "GPRF"

    def __post_init__(self):
        """Set default parameters if not provided."""
        if not self.parameters:
            self.parameters = {
                "frequency_hz": 1e9,
                "generator_level_dbm": -80.0,
                "expected_power_dbm": 10.0,
                "arb_file": "",
                "statistic_count": 100,
                "meas_length_s": 0.01,
            }

    @classmethod
    def create(
        cls,
        frequency_hz: float = 1e9,
        generator_level_dbm: float = -80.0,
        expected_power_dbm: float = 10.0,
        arb_file: str = "",
    ) -> "NonSignalingRxTemplate":
        """
        Create a non-signaling RX test template.

        Args:
            frequency_hz: Test frequency in Hz
            generator_level_dbm: Generator output level in dBm
            expected_power_dbm: Expected DUT TX power in dBm
            arb_file: ARB waveform file path on CMW500

        Returns:
            Configured NonSignalingRxTemplate
        """
        return cls(
            parameters={
                "frequency_hz": frequency_hz,
                "generator_level_dbm": generator_level_dbm,
                "expected_power_dbm": expected_power_dbm,
                "arb_file": arb_file,
                "statistic_count": 100,
                "meas_length_s": 0.01,
            }
        )

    async def apply(self, cmw) -> None:
        """
        Apply non-signaling RX test configuration to CMW500.

        Args:
            cmw: CMW500Driver instance
        """
        from ..models.cmw_types import SignalPath

        freq = self.parameters["frequency_hz"]

        # Configure generator
        await cmw.gen_set_frequency(freq)
        await cmw.gen_set_level(self.parameters["generator_level_dbm"])

        # Load ARB file if specified
        arb_file = self.parameters.get("arb_file", "")
        if arb_file:
            await cmw.gen_load_arb(arb_file)

        # Configure analyzer
        await cmw.set_signal_path(SignalPath.STANDALONE)
        await cmw.meas_set_frequency(freq)
        await cmw.meas_set_expected_power(self.parameters["expected_power_dbm"])
        await cmw.meas_configure_power(
            statistic_count=self.parameters.get("statistic_count", 100),
            meas_length_s=self.parameters.get("meas_length_s", 0.01),
        )

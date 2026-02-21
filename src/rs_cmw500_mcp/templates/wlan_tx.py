"""WLAN TX measurement template for CMW500."""

from dataclasses import dataclass

from .base import MeasurementTemplate


@dataclass
class WLANTxTemplate(MeasurementTemplate):
    """
    WLAN 802.11ax TX measurement template.

    Configures CMW500 for WLAN TX power and modulation quality
    measurement across various 802.11 standards and bandwidths.
    """

    name: str = "WLAN 802.11ax 80 MHz TX"
    description: str = "WLAN 802.11ax 80 MHz TX power and modulation quality measurement"
    technology: str = "WLAN"

    def __post_init__(self):
        """Set default parameters if not provided."""
        if not self.parameters:
            self.parameters = {
                "technology": "wlan",
                "standard": "802.11ax",
                "bandwidth_mhz": 80,
                "channel": 36,
                "frequency_hz": 5.18e9,
                "expected_power_dbm": 20.0,
            }

    @classmethod
    def wifi6_80mhz(cls) -> "WLANTxTemplate":
        """Create WLAN 802.11ax 80 MHz TX template."""
        return cls(
            name="WLAN 802.11ax 80 MHz TX",
            description="WLAN 802.11ax 80 MHz TX power and modulation quality measurement",
            parameters={
                "technology": "wlan",
                "standard": "802.11ax",
                "bandwidth_mhz": 80,
                "channel": 36,
                "frequency_hz": 5.18e9,
                "expected_power_dbm": 20.0,
            },
        )

    @classmethod
    def wifi6_40mhz(cls) -> "WLANTxTemplate":
        """Create WLAN 802.11ax 40 MHz TX template."""
        return cls(
            name="WLAN 802.11ax 40 MHz TX",
            description="WLAN 802.11ax 40 MHz TX measurement",
            parameters={
                "technology": "wlan",
                "standard": "802.11ax",
                "bandwidth_mhz": 40,
                "channel": 36,
                "frequency_hz": 5.19e9,
                "expected_power_dbm": 20.0,
            },
        )

    @classmethod
    def wifi5_80mhz(cls) -> "WLANTxTemplate":
        """Create WLAN 802.11ac 80 MHz TX template."""
        return cls(
            name="WLAN 802.11ac 80 MHz TX",
            description="WLAN 802.11ac 80 MHz TX measurement",
            parameters={
                "technology": "wlan",
                "standard": "802.11ac",
                "bandwidth_mhz": 80,
                "channel": 36,
                "frequency_hz": 5.18e9,
                "expected_power_dbm": 20.0,
            },
        )

    async def apply(self, cmw) -> None:
        """
        Apply WLAN TX measurement configuration to CMW500.

        Args:
            cmw: CMW500Driver instance
        """
        from ..models.cmw_types import SignalPath

        # Set signal path to standalone for WLAN measurements
        await cmw.set_signal_path(SignalPath.STANDALONE)

        # Configure analyzer for WLAN measurement
        await cmw.meas_set_frequency(self.parameters["frequency_hz"])
        await cmw.meas_set_expected_power(self.parameters["expected_power_dbm"])

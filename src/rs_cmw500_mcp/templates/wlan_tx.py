"""WLAN TX measurement template for CMW500."""

from dataclasses import dataclass

from .base import MeasurementTemplate


@dataclass
class WLANTxTemplate(MeasurementTemplate):
    """
    WLAN 802.11ax TX measurement template.

    Configures CMW500 for WLAN TX power and modulation quality
    measurement across various 802.11 standards and bandwidths.
    Uses the native WLAN SCPI subsystem for proper configuration.
    """

    name: str = "WLAN 802.11ax 80 MHz TX"
    description: str = "WLAN 802.11ax 80 MHz TX power and modulation quality measurement"
    technology: str = "WLAN"

    def __post_init__(self):
        """Set default parameters if not provided."""
        if not self.parameters:
            self.parameters = {
                "technology": "wlan",
                "standard": "AX",
                "bandwidth": "BW80",
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
                "standard": "AX",
                "bandwidth": "BW80",
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
                "standard": "AX",
                "bandwidth": "BW40",
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
                "standard": "AC",
                "bandwidth": "BW80",
                "channel": 36,
                "frequency_hz": 5.18e9,
                "expected_power_dbm": 20.0,
            },
        )

    async def apply(self, cmw) -> None:
        """
        Apply WLAN TX measurement configuration to CMW500.

        Uses the native WLAN SCPI subsystem for proper measurement setup.

        Args:
            cmw: CMW500Driver instance
        """
        from ..models.cmw_types import WLANBandwidth, WLANMeasConfig, WLANStandard

        config = WLANMeasConfig(
            standard=WLANStandard(self.parameters.get("standard", "AX")),
            bandwidth=WLANBandwidth(self.parameters.get("bandwidth", "BW80")),
            frequency_hz=self.parameters.get("frequency_hz", 5.18e9),
            expected_power_dbm=self.parameters.get("expected_power_dbm", 20.0),
        )
        await cmw.wlan_configure(config)

"""WLAN RX sensitivity test template for CMW500."""

from dataclasses import dataclass

from .base import MeasurementTemplate


@dataclass
class WLANRxTemplate(MeasurementTemplate):
    """
    WLAN RX sensitivity test template.

    Configures CMW500 generator to output a WLAN-modulated signal
    at controlled power levels for DUT receiver sensitivity testing.
    Uses GPRF generator with ARB waveform for the TX side.
    """

    name: str = "WLAN 802.11ax RX Sensitivity"
    description: str = "WLAN 802.11ax RX sensitivity test with generator"
    technology: str = "WLAN"

    def __post_init__(self):
        """Set default parameters if not provided."""
        if not self.parameters:
            self.parameters = {
                "standard": "AX",
                "bandwidth": "BW80",
                "frequency_hz": 5.18e9,
                "generator_level_dbm": -70.0,
                "arb_file": "",
            }

    @classmethod
    def wifi6_80mhz(cls) -> "WLANRxTemplate":
        """Create WLAN 802.11ax 80 MHz RX sensitivity template."""
        return cls(
            name="WLAN 802.11ax 80 MHz RX Sensitivity",
            description="WLAN 802.11ax 80 MHz RX sensitivity test",
            parameters={
                "standard": "AX",
                "bandwidth": "BW80",
                "frequency_hz": 5.18e9,
                "generator_level_dbm": -70.0,
                "arb_file": "",
            },
        )

    @classmethod
    def wifi6_40mhz(cls) -> "WLANRxTemplate":
        """Create WLAN 802.11ax 40 MHz RX sensitivity template."""
        return cls(
            name="WLAN 802.11ax 40 MHz RX Sensitivity",
            description="WLAN 802.11ax 40 MHz RX sensitivity test",
            parameters={
                "standard": "AX",
                "bandwidth": "BW40",
                "frequency_hz": 5.19e9,
                "generator_level_dbm": -70.0,
                "arb_file": "",
            },
        )

    async def apply(self, cmw) -> None:
        """Apply WLAN RX sensitivity test configuration to CMW500.

        Configures the GPRF generator to output a WLAN-modulated signal.

        Args:
            cmw: CMW500Driver instance
        """
        freq = self.parameters["frequency_hz"]
        level = self.parameters.get("generator_level_dbm", -70.0)

        await cmw.gen_set_frequency(freq)
        await cmw.gen_set_level(level)

        arb_file = self.parameters.get("arb_file", "")
        if arb_file:
            await cmw.gen_load_arb(arb_file)

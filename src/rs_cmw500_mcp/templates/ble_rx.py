"""BLE RX sensitivity test template for CMW500."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .base import MeasurementTemplate

if TYPE_CHECKING:
    from ..driver.cmw500_driver import CMW500Driver


@dataclass
class BLERxTemplate(MeasurementTemplate):
    """
    BLE RX sensitivity test template.

    Configures CMW500 generator to output a BLE-modulated signal
    at controlled power levels for DUT receiver sensitivity testing.
    Uses GPRF generator with ARB waveform for the TX side.
    """

    name: str = "BLE 1M RX Sensitivity"
    description: str = "BLE 1M PHY RX sensitivity test with generator"
    technology: str = "Bluetooth"

    def __post_init__(self) -> None:
        """Set default parameters if not provided."""
        if not self.parameters:
            self.parameters = {
                "ble_mode": "LE1M",
                "frequency_hz": 2.402e9,
                "generator_level_dbm": -70.0,
                "arb_file": "",
            }

    @classmethod
    def ble_1m(cls) -> "BLERxTemplate":
        """Create BLE 1M PHY RX sensitivity template."""
        return cls(
            name="BLE 1M RX Sensitivity",
            description="BLE 1M PHY RX sensitivity test",
            parameters={
                "ble_mode": "LE1M",
                "frequency_hz": 2.402e9,
                "generator_level_dbm": -70.0,
                "arb_file": "",
            },
        )

    @classmethod
    def ble_2m(cls) -> "BLERxTemplate":
        """Create BLE 2M PHY RX sensitivity template."""
        return cls(
            name="BLE 2M RX Sensitivity",
            description="BLE 2M PHY RX sensitivity test",
            parameters={
                "ble_mode": "LE2M",
                "frequency_hz": 2.402e9,
                "generator_level_dbm": -70.0,
                "arb_file": "",
            },
        )

    async def apply(self, cmw: "CMW500Driver") -> None:
        """Apply BLE RX sensitivity test configuration to CMW500.

        Configures the GPRF generator to output a BLE-modulated signal.

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

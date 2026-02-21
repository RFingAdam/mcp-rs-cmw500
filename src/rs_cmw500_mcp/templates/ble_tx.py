"""BLE TX measurement template for CMW500."""

from dataclasses import dataclass

from .base import MeasurementTemplate


@dataclass
class BLETxTemplate(MeasurementTemplate):
    """
    BLE TX measurement template.

    Configures CMW500 for BLE non-signaling TX measurements
    including power, modulation (DEVM), and frequency error.
    """

    name: str = "BLE 1M TX"
    description: str = "BLE 1M PHY TX power and modulation measurement"
    technology: str = "Bluetooth"

    def __post_init__(self):
        """Set default parameters if not provided."""
        if not self.parameters:
            self.parameters = {
                "technology": "LENergy",
                "ble_mode": "LE1M",
                "frequency_hz": 2.402e9,
                "expected_power_dbm": 10.0,
            }

    @classmethod
    def ble_1m(cls) -> "BLETxTemplate":
        """Create BLE 1M PHY TX template (2402 MHz, channel 37)."""
        return cls(
            name="BLE 1M TX",
            description="BLE 1M PHY TX power and modulation measurement",
            parameters={
                "technology": "LENergy",
                "ble_mode": "LE1M",
                "frequency_hz": 2.402e9,
                "expected_power_dbm": 10.0,
            },
        )

    @classmethod
    def ble_2m(cls) -> "BLETxTemplate":
        """Create BLE 2M PHY TX template (2402 MHz, channel 37)."""
        return cls(
            name="BLE 2M TX",
            description="BLE 2M PHY TX power and modulation measurement",
            parameters={
                "technology": "LENergy",
                "ble_mode": "LE2M",
                "frequency_hz": 2.402e9,
                "expected_power_dbm": 10.0,
            },
        )

    @classmethod
    def ble_coded_s2(cls) -> "BLETxTemplate":
        """Create BLE Coded S=2 PHY TX template."""
        return cls(
            name="BLE Coded S2 TX",
            description="BLE Coded S=2 PHY TX measurement",
            parameters={
                "technology": "LENergy",
                "ble_mode": "LECS2",
                "frequency_hz": 2.402e9,
                "expected_power_dbm": 10.0,
            },
        )

    async def apply(self, cmw) -> None:
        """Apply BLE TX measurement configuration to CMW500.

        Args:
            cmw: CMW500Driver instance
        """
        from ..models.cmw_types import BLEMode, BTMeasConfig, BTTechnology

        config = BTMeasConfig(
            technology=BTTechnology(self.parameters.get("technology", "LENergy")),
            ble_mode=BLEMode(self.parameters.get("ble_mode", "LE1M")),
            frequency_hz=self.parameters.get("frequency_hz", 2.402e9),
            expected_power_dbm=self.parameters.get("expected_power_dbm", 10.0),
        )
        await cmw.bt_configure(config)

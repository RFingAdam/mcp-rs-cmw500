"""Bluetooth Classic TX measurement template for CMW500."""

from dataclasses import dataclass

from .base import MeasurementTemplate


@dataclass
class BTClassicTxTemplate(MeasurementTemplate):
    """
    Bluetooth Classic TX measurement template.

    Configures CMW500 for Bluetooth Classic non-signaling TX measurements
    including power, modulation (DEVM), and frequency accuracy.
    """

    name: str = "BT Classic DH1 TX"
    description: str = "Bluetooth Classic DH1 TX power and modulation measurement"
    technology: str = "Bluetooth"

    def __post_init__(self):
        """Set default parameters if not provided."""
        if not self.parameters:
            self.parameters = {
                "technology": "CLASsic",
                "packet_type": "DH1",
                "frequency_hz": 2.402e9,
                "expected_power_dbm": 10.0,
            }

    @classmethod
    def dh1(cls) -> "BTClassicTxTemplate":
        """Create BT Classic DH1 TX template."""
        return cls(
            name="BT Classic DH1 TX",
            description="Bluetooth Classic DH1 TX measurement",
            parameters={
                "technology": "CLASsic",
                "packet_type": "DH1",
                "frequency_hz": 2.402e9,
                "expected_power_dbm": 10.0,
            },
        )

    @classmethod
    def dh5(cls) -> "BTClassicTxTemplate":
        """Create BT Classic DH5 TX template."""
        return cls(
            name="BT Classic DH5 TX",
            description="Bluetooth Classic DH5 TX measurement",
            parameters={
                "technology": "CLASsic",
                "packet_type": "DH5",
                "frequency_hz": 2.402e9,
                "expected_power_dbm": 10.0,
            },
        )

    async def apply(self, cmw) -> None:
        """Apply BT Classic TX measurement configuration to CMW500.

        Args:
            cmw: CMW500Driver instance
        """
        from ..models.cmw_types import BTMeasConfig, BTPacketType, BTTechnology

        config = BTMeasConfig(
            technology=BTTechnology(self.parameters.get("technology", "CLASsic")),
            packet_type=BTPacketType(self.parameters.get("packet_type", "DH1")),
            frequency_hz=self.parameters.get("frequency_hz", 2.402e9),
            expected_power_dbm=self.parameters.get("expected_power_dbm", 10.0),
        )
        await cmw.bt_configure(config)

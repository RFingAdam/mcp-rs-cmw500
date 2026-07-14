"""LTE TX power measurement template."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..models.cmw_types import CellConfig
from .base import MeasurementTemplate

if TYPE_CHECKING:
    from ..driver.cmw500_driver import CMW500Driver


@dataclass
class LTETxPowerTemplate(MeasurementTemplate):
    """
    Template for LTE TX power measurement.

    Configures CMW500 for LTE signaling mode TX power measurement
    including cell parameters, bandwidth, and expected power levels.
    """

    name: str = "LTE TX Power"
    description: str = "LTE TX power measurement in signaling mode"
    technology: str = "LTE"

    def __post_init__(self) -> None:
        """Set default parameters if not provided."""
        if not self.parameters:
            self.parameters = {
                "band": 1,
                "bandwidth_mhz": 10.0,
                "dl_earfcn": 300,
                "dl_level_dbm": -60.0,
                "expected_power_dbm": 23.0,
                "mcc": "001",
                "mnc": "01",
            }

    @classmethod
    def create(
        cls,
        band: int = 1,
        bandwidth_mhz: float = 10.0,
        dl_earfcn: int = 300,
        dl_level_dbm: float = -60.0,
        expected_power_dbm: float = 23.0,
    ) -> "LTETxPowerTemplate":
        """
        Create an LTE TX power template with specified parameters.

        Args:
            band: LTE band number
            bandwidth_mhz: Channel bandwidth in MHz
            dl_earfcn: Downlink EARFCN
            dl_level_dbm: Downlink level in dBm
            expected_power_dbm: Expected UE TX power in dBm

        Returns:
            Configured LTETxPowerTemplate
        """
        return cls(
            parameters={
                "band": band,
                "bandwidth_mhz": bandwidth_mhz,
                "dl_earfcn": dl_earfcn,
                "dl_level_dbm": dl_level_dbm,
                "expected_power_dbm": expected_power_dbm,
                "mcc": "001",
                "mnc": "01",
            }
        )

    async def apply(self, cmw: "CMW500Driver") -> None:
        """
        Apply LTE TX measurement configuration to CMW500.

        Args:
            cmw: CMW500Driver instance
        """
        config = CellConfig(
            band=self.parameters.get("band", 1),
            bandwidth_mhz=self.parameters.get("bandwidth_mhz", 10.0),
            dl_earfcn=self.parameters.get("dl_earfcn", 300),
            dl_level_dbm=self.parameters.get("dl_level_dbm", -60.0),
            mcc=self.parameters.get("mcc", "001"),
            mnc=self.parameters.get("mnc", "01"),
        )

        await cmw.lte_configure_cell(config)
        await cmw.lte_configure_nas(config.mcc, config.mnc)
        await cmw.lte_meas_configure()

"""Measurement templates for common CMW500 test scenarios."""

from .base import MeasurementTemplate
from .ble_rx import BLERxTemplate
from .ble_tx import BLETxTemplate
from .bt_classic_tx import BTClassicTxTemplate
from .gprf_power import GPRFPowerTemplate
from .lte_tx import LTETxPowerTemplate
from .nonsig_rx import NonSignalingRxTemplate
from .wlan_rx import WLANRxTemplate
from .wlan_tx import WLANTxTemplate

__all__ = [
    "BLERxTemplate",
    "BLETxTemplate",
    "BTClassicTxTemplate",
    "GPRFPowerTemplate",
    "LTETxPowerTemplate",
    "MeasurementTemplate",
    "NonSignalingRxTemplate",
    "WLANRxTemplate",
    "WLANTxTemplate",
]

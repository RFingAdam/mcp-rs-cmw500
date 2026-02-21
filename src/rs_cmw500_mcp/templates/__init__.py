"""Measurement templates for common CMW500 test scenarios."""

from .base import MeasurementTemplate
from .gprf_power import GPRFPowerTemplate
from .lte_tx import LTETxPowerTemplate
from .nonsig_rx import NonSignalingRxTemplate
from .wlan_tx import WLANTxTemplate

__all__ = [
    "GPRFPowerTemplate",
    "LTETxPowerTemplate",
    "MeasurementTemplate",
    "NonSignalingRxTemplate",
    "WLANTxTemplate",
]

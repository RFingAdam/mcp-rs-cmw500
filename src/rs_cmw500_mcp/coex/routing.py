"""RF routing validation for simultaneous multi-technology (coex) operation.

Running two technologies at once on one CMW500 requires each signaling/generator
block to use a *distinct* RF connector/converter; sharing one causes contention.
This module provides a pure, hardware-free guard. The physical routing itself is
configured on the instrument (GUI or raw SCPI ROUTe commands) — the server cannot
enforce cabling, only catch an obvious connector collision before a long sweep.
"""

from __future__ import annotations


class RoutingError(ValueError):
    """Raised when two subsystems are assigned the same RF connector."""


def validate_routing(connectors: dict[str, str]) -> None:
    """Ensure every subsystem maps to a distinct, non-empty RF connector.

    Args:
        connectors: subsystem name -> connector label
            (e.g. {"lte": "RF1COM", "ble": "RF2COM"}).

    Raises:
        RoutingError: if two subsystems share a connector, or a label is blank.
    """
    seen: dict[str, str] = {}
    for subsystem, connector in connectors.items():
        label = (connector or "").strip().upper()
        if not label:
            raise RoutingError(f"No RF connector assigned for '{subsystem}'.")
        if label in seen:
            raise RoutingError(
                f"RF connector {connector!r} is shared by '{seen[label]}' and "
                f"'{subsystem}'. Use a separate connector per technology for coex."
            )
        seen[label] = subsystem

"""Map installed CMW500 options (*OPT?) to server capability domains.

The token lists are best-effort and must be verified against a real unit's
*OPT? output — option strings vary by firmware and datasheet revision. The map
is data-driven so it is trivial to correct after the first live read.
"""

from __future__ import annotations

# domain -> option tokens (case-insensitive substring match against *OPT? entries).
DOMAIN_OPTIONS: dict[str, list[str]] = {
    "lte_signaling": ["KS500", "KS510", "KS520"],
    "lte_measurement": ["KM500", "KM050"],
    "ble_bt_signaling": ["KS600", "KS610"],
    "wlan_signaling": ["KS650", "KS651"],
    "wlan_throughput": ["B450", "KM050"],
    "gsm_signaling": ["KS200", "KS201", "KM200"],
    "wcdma_signaling": ["KS400", "KS410", "KM400"],
    "gprf": ["KM010", "B110", "B100"],
}


def domains_for_options(options: list[str]) -> dict[str, bool]:
    """Return {domain: licensed?} by matching option tokens against *OPT? output."""
    upper = [o.upper() for o in options]
    result: dict[str, bool] = {}
    for domain, tokens in DOMAIN_OPTIONS.items():
        result[domain] = any(any(tok in opt for opt in upper) for tok in tokens)
    return result

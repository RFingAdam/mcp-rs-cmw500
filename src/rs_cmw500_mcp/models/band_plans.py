"""RF band-plan data and coexistence math for the CMW500 MCP server.

This module holds *standard* RF facts only (3GPP EARFCN tables, band edges,
ISM / sub-GHz / GNSS ranges, BLE channel arithmetic) plus the pure-computation
intermodulation (IMD) engine used by the coexistence planner tools. None of this
is customer- or product-specific; product-tied *selections* (e.g. which subset of
bands a given DUT cares about) live in an overridable presets file, not here.

References: 3GPP TS 36.101 (E-UTRA), Bluetooth Core (LE channel map).
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# BLE channel arithmetic (Bluetooth Core)
# ---------------------------------------------------------------------------

#: BLE data-channel indices used for the LE 1M PHY receiver test (0..39).
BLE_DATA_CHANNEL_MIN = 0
BLE_DATA_CHANNEL_MAX = 39

#: Advertising channels, excluded from data-channel PER sweeps.
BLE_ADV_CHANNELS: frozenset[int] = frozenset({0, 12, 39})


def ble_channel_to_freq_mhz(channel: int) -> float:
    """Return the BLE channel center frequency in MHz (2402 + 2*ch)."""
    if not BLE_DATA_CHANNEL_MIN <= channel <= BLE_DATA_CHANNEL_MAX:
        raise ValueError(f"BLE channel {channel} out of range 0..39")
    return 2402.0 + 2.0 * channel


def generate_ble_channels(
    start_ch: int = 1,
    end_ch: int = 38,
    spacing: int = 1,
    skip_adv: bool = True,
) -> list[int]:
    """Build an inclusive list of BLE data channels, optionally skipping the
    advertising channels {0, 12, 39}."""
    if spacing < 1:
        raise ValueError("spacing must be >= 1")
    adv = BLE_ADV_CHANNELS if skip_adv else frozenset()
    channels: list[int] = []
    current = start_ch
    while current <= end_ch:
        if current not in adv:
            channels.append(int(current))
        current += spacing
    if channels and channels[-1] != end_ch and end_ch not in adv:
        channels.append(int(end_ch))
    return channels


# ---------------------------------------------------------------------------
# LTE FDD EARFCN <-> frequency (3GPP TS 36.101)
# ---------------------------------------------------------------------------

# band -> (f_dl_low_mhz, n_offs_dl, f_ul_low_mhz, n_offs_ul, earfcn_min, earfcn_max)
LTE_FDD_BANDS: dict[int, tuple[float, int, float, int, int, int]] = {
    1: (2110.0, 0, 1920.0, 18000, 0, 599),
    2: (1930.0, 600, 1850.0, 18600, 600, 1199),
    3: (1805.0, 1200, 1710.0, 19200, 1200, 1949),
    4: (2110.0, 1950, 1710.0, 19950, 1950, 2399),
    5: (869.0, 2400, 824.0, 20400, 2400, 2649),
    7: (2620.0, 2750, 2500.0, 20750, 2750, 3449),
    8: (925.0, 3450, 880.0, 21450, 3450, 3799),
    9: (1844.9, 3800, 1749.9, 21800, 3800, 4149),
    12: (729.0, 5010, 699.0, 23010, 5010, 5179),
    13: (746.0, 5180, 777.0, 23180, 5180, 5279),
    14: (758.0, 5280, 788.0, 23280, 5280, 5379),
    18: (860.0, 5850, 815.0, 23850, 5850, 5999),
    19: (875.0, 6000, 830.0, 24000, 6000, 6149),
    20: (791.0, 6150, 832.0, 24150, 6150, 6449),
    25: (1930.0, 8040, 1850.0, 26040, 8040, 8689),
    26: (859.0, 8690, 814.0, 26690, 8690, 9039),
    28: (758.0, 9210, 703.0, 27210, 9210, 9659),
}


def band_for_earfcn(earfcn: int) -> int | None:
    """Return the FDD band number that contains the given DL EARFCN, or None."""
    for band, (_fdl, _ndl, _ful, _nul, n_min, n_max) in LTE_FDD_BANDS.items():
        if n_min <= earfcn <= n_max:
            return band
    return None


def earfcn_to_frequencies(earfcn: int) -> tuple[int | None, float | None, float | None]:
    """Map a DL EARFCN to (band, dl_freq_mhz, ul_freq_mhz) per TS 36.101.

    Returns (None, None, None) if the EARFCN is not in a supported FDD band.
    """
    for band, (f_dl, n_dl, f_ul, _n_ul, n_min, n_max) in LTE_FDD_BANDS.items():
        if n_min <= earfcn <= n_max:
            # `earfcn` is a DL EARFCN. The channel offset within the band
            # (earfcn - n_dl) is shared by UL and DL, so both frequencies use it.
            # (The source script erroneously subtracted n_ul here, yielding bogus
            # UL frequencies; the paired UL RF frequency is computed correctly below.)
            offset = earfcn - n_dl
            dl = round(f_dl + 0.1 * offset, 2)
            ul = round(f_ul + 0.1 * offset, 2)
            return band, dl, ul
    return None, None, None


def earfcn_range(band: int) -> tuple[int, int]:
    """Return the (min, max) DL EARFCN range for an FDD band."""
    if band not in LTE_FDD_BANDS:
        raise ValueError(f"Unsupported/unknown LTE FDD band: {band}")
    _fdl, _ndl, _ful, _nul, n_min, n_max = LTE_FDD_BANDS[band]
    return n_min, n_max


def generate_lte_earfcns(band: int, spacing: int = 25, edge_trim: int = 25) -> list[int]:
    """Sweep EARFCNs across a band, trimmed off both edges by ``edge_trim``.

    Mirrors the proven sweep from the source sensitivity scripts: start at
    ``min+trim``, step by ``spacing``, and always include the trimmed top edge.
    """
    if spacing < 1:
        raise ValueError("spacing must be >= 1")
    n_min, n_max = earfcn_range(band)
    start = n_min + edge_trim
    end = n_max - edge_trim
    if end < start:
        return [n_min + (n_max - n_min) // 2]
    channels: list[int] = []
    current = start
    while current <= end:
        channels.append(int(current))
        current += spacing
    if not channels or channels[-1] != end:
        channels.append(int(end))
    return channels


# ---------------------------------------------------------------------------
# RF band edges for coexistence / IMD planning
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BandEdges:
    """Uplink and downlink frequency edges of a band, in MHz.

    For unpaired/ISM bands the UL and DL edges are identical. Aggressors
    transmit on ``ul_*``; victims receive on ``dl_*``.
    """

    display: str
    ul_start: float
    ul_end: float
    dl_start: float
    dl_end: float
    is_lte: bool = False

    @property
    def ul_center(self) -> float:
        return (self.ul_start + self.ul_end) / 2.0

    @property
    def ul_bandwidth(self) -> float:
        return self.ul_end - self.ul_start

    @property
    def dl_center(self) -> float:
        return (self.dl_start + self.dl_end) / 2.0


def _ism(display: str, start: float, end: float) -> BandEdges:
    return BandEdges(display, start, end, start, end)


# Canonical, neutral band keys. Standard allocations only.
BAND_EDGES: dict[str, BandEdges] = {
    "GNSS_L1": _ism("GNSS L1", 1563.0, 1587.0),
    "WIFI_BLE_2G4": _ism("Wi-Fi/BLE 2.4 GHz", 2400.0, 2483.5),
    "WIFI5_LOW": _ism("Wi-Fi 5 (low)", 5150.0, 5250.0),
    "WIFI5_HIGH": _ism("Wi-Fi 5 (high)", 5735.0, 5835.0),
    "HALOW_EU": _ism("802.11ah HaLow EU", 863.0, 868.0),
    "HALOW_US": _ism("802.11ah HaLow US", 902.0, 928.0),
}

# LTE bands: UL/DL edges (MHz) from 3GPP band definitions.
_LTE_EDGES: dict[int, tuple[float, float, float, float]] = {
    1: (1920, 1980, 2110, 2170),
    2: (1850, 1910, 1930, 1990),
    3: (1710, 1785, 1805, 1880),
    4: (1710, 1755, 2110, 2155),
    5: (824, 849, 869, 894),
    7: (2500, 2570, 2620, 2690),
    8: (880, 915, 925, 960),
    9: (1749.9, 1784.9, 1844.9, 1879.9),
    12: (699, 716, 729, 746),
    13: (777, 787, 746, 756),
    14: (788, 798, 758, 768),
    18: (815, 830, 860, 875),
    19: (830, 845, 875, 890),
    20: (832, 862, 791, 821),
    25: (1850, 1915, 1930, 1995),
    26: (814, 849, 859, 894),
    28: (703, 748, 758, 803),
}
for _b, (_us, _ue, _ds, _de) in _LTE_EDGES.items():
    BAND_EDGES[f"LTE_B{_b}"] = BandEdges(f"LTE B{_b}", _us, _ue, _ds, _de, is_lte=True)


def get_band_edges(name: str) -> BandEdges:
    """Look up band edges by canonical key (case-insensitive)."""
    key = name.strip().upper().replace(" ", "_").replace("-", "_").replace("/", "_")
    # Accept a few friendly aliases.
    aliases = {
        "GNSS": "GNSS_L1",
        "L1": "GNSS_L1",
        "WIFI": "WIFI_BLE_2G4",
        "BLE": "WIFI_BLE_2G4",
        "WIFI_2G4": "WIFI_BLE_2G4",
        "WIFI_BLE_2.4G": "WIFI_BLE_2G4",
    }
    key = aliases.get(key, key)
    if key not in BAND_EDGES:
        raise ValueError(f"Unknown band {name!r}. Known: {', '.join(sorted(BAND_EDGES))}")
    return BAND_EDGES[key]


# ---------------------------------------------------------------------------
# Intermodulation / harmonic engine (pure computation, no instrument)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImdProduct:
    """One intermodulation or harmonic product."""

    order: int
    equation: str
    center_mhz: float
    bandwidth_mhz: float
    start_mhz: float
    end_mhz: float

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "order": self.order,
            "equation": self.equation,
            "center_mhz": round(self.center_mhz, 4),
            "bandwidth_mhz": round(self.bandwidth_mhz, 4),
            "start_mhz": round(self.start_mhz, 4),
            "end_mhz": round(self.end_mhz, 4),
        }

    def overlaps(self, victim_start: float, victim_end: float) -> bool:
        """True if this product's band overlaps the victim receive band."""
        return (self.start_mhz < victim_end) and (self.end_mhz > victim_start)


def intermod_products(
    f1_start: float,
    f1_end: float,
    f2_start: float,
    f2_end: float,
    max_order: int = 7,
) -> list[ImdProduct]:
    """Two-carrier intermodulation products |m*f1 + n*f2| for orders 2..max_order.

    Bandwidth-aware: product bandwidth is |m|*bw1 + |n|*bw2. Only mixing products
    (both m and n non-zero) are returned; pure harmonics come from
    :func:`harmonic_products`.
    """
    f1c, bw1 = (f1_start + f1_end) / 2.0, f1_end - f1_start
    f2c, bw2 = (f2_start + f2_end) / 2.0, f2_end - f2_start
    products: list[ImdProduct] = []
    for order in range(2, max_order + 1):
        for m in range(-order, order + 1):
            for n in range(-order, order + 1):
                if abs(m) + abs(n) != order:
                    continue
                if m == 0 or n == 0:
                    continue  # harmonic, not a mixing product
                # Canonical sign convention: fix m > 0 to avoid listing a product
                # and its exact negative twice.
                if m < 0:
                    continue
                center = abs(m * f1c + n * f2c)
                if center <= 0.1:
                    continue
                bw = abs(m) * bw1 + abs(n) * bw2
                products.append(
                    ImdProduct(
                        order=order,
                        equation=f"|{m}*f1 {'+' if n >= 0 else '-'} {abs(n)}*f2|",
                        center_mhz=center,
                        bandwidth_mhz=bw,
                        start_mhz=center - bw / 2.0,
                        end_mhz=center + bw / 2.0,
                    )
                )
    return products


def harmonic_products(
    f_start: float, f_end: float, max_order: int = 7, carrier_label: str = "f1"
) -> list[ImdProduct]:
    """Single-carrier harmonics (2f, 3f, ... up to max_order)."""
    fc, bw = (f_start + f_end) / 2.0, f_end - f_start
    products: list[ImdProduct] = []
    for order in range(2, max_order + 1):
        center = order * fc
        b = order * bw
        products.append(
            ImdProduct(
                order=order,
                equation=f"{order}*{carrier_label}",
                center_mhz=center,
                bandwidth_mhz=b,
                start_mhz=center - b / 2.0,
                end_mhz=center + b / 2.0,
            )
        )
    return products


# Constraint profiles for batch analysis. A profile decides which carrier
# combinations are physically meaningful for a given radio architecture.
CONSTRAINT_PROFILES: dict[str, str] = {
    "none": "No filtering; enumerate every combination.",
    "single_radio": (
        "One shared front end: no dual-LTE, no LTE carrier when the victim is "
        "LTE, no Wi-Fi 5 low+high together, no HaLow US+EU together."
    ),
}


def combination_allowed(c1: str, c2: str, victim: str, profile: str = "single_radio") -> bool:
    """Return True if a two-carrier combination is allowed under ``profile``."""
    if profile == "none":
        return True
    e1, e2, ev = get_band_edges(c1), get_band_edges(c2), get_band_edges(victim)
    if ev.is_lte and (e1.is_lte or e2.is_lte):
        return False  # can't Tx/Rx LTE simultaneously on one radio
    if e1.is_lte and e2.is_lte:
        return False  # no dual-LTE aggressor
    pair = {c1.upper(), c2.upper()}
    if {"WIFI5_LOW", "WIFI5_HIGH"} <= pair:
        return False
    if {"HALOW_US", "HALOW_EU"} <= pair:
        return False
    return True

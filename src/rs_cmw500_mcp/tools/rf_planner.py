"""Coexistence / intermodulation frequency-planner tools (pure computation).

These tools need no instrument connection. They compute which harmonic and
intermodulation products fall into a victim receive band, so an operator can
decide which aggressor bands/channels are worth exercising in a live coex sweep.
"""

import logging
from itertools import combinations_with_replacement
from typing import Any

from mcp.types import CallToolResult, Tool

from ..models.band_plans import (
    BAND_EDGES,
    CONSTRAINT_PROFILES,
    BandEdges,
    combination_allowed,
    get_band_edges,
    harmonic_products,
    intermod_products,
)
from .registry import registry
from .shared import _format_result

logger = logging.getLogger(__name__)


def _resolve_edges(spec: str) -> tuple[BandEdges | None, tuple[float, float]]:
    """Resolve a band spec to (BandEdges|None, (start_mhz, end_mhz)).

    ``spec`` is either a known band key (e.g. ``"LTE_B7"``, ``"HALOW_US"``) or an
    explicit ``"start-end"`` MHz range (e.g. ``"902-928"``).
    """
    s = spec.strip()
    if "-" in s and all(part.replace(".", "").strip().isdigit() for part in s.split("-", 1)):
        lo, hi = (float(x) for x in s.split("-", 1))
        if hi < lo:
            lo, hi = hi, lo
        return None, (lo, hi)
    edges = get_band_edges(s)
    return edges, (edges.ul_start, edges.ul_end)


def _carrier_edges(spec: str) -> tuple[str, float, float]:
    """Return (label, ul_start, ul_end) for an aggressor carrier."""
    edges, (lo, hi) = _resolve_edges(spec)
    label = edges.display if edges else f"{lo}-{hi} MHz"
    return label, lo, hi


def _victim_band(spec: str) -> tuple[str, float, float]:
    """Return (label, dl_start, dl_end) for a victim receiver band."""
    edges, (lo, hi) = _resolve_edges(spec)
    if edges:
        return edges.display, edges.dl_start, edges.dl_end
    return f"{lo}-{hi} MHz", lo, hi


async def _handle_imd_analyze(args: dict[str, Any]) -> CallToolResult:
    """Analyze harmonic + intermod hits from one or two carriers into a victim."""
    max_order = int(args.get("max_order", 7))
    include_harmonics = bool(args.get("include_harmonics", True))

    v_label, v_start, v_end = _victim_band(args["victim"])
    c1_label, f1s, f1e = _carrier_edges(args["carrier1"])

    hits: list[dict[str, Any]] = []
    evaluated = 0

    def _add(products: list[Any], source: str, carriers: str) -> None:
        nonlocal evaluated
        for p in products:
            evaluated += 1
            if p.overlaps(v_start, v_end):
                row = p.to_dict()
                row["source"] = source
                row["carriers"] = carriers
                hits.append(row)

    if include_harmonics:
        _add(harmonic_products(f1s, f1e, max_order, "f1"), "harmonic", c1_label)

    if args.get("carrier2"):
        c2_label, f2s, f2e = _carrier_edges(args["carrier2"])
        if include_harmonics:
            _add(harmonic_products(f2s, f2e, max_order, "f2"), "harmonic", c2_label)
        _add(
            intermod_products(f1s, f1e, f2s, f2e, max_order),
            "IMD",
            f"{c1_label} + {c2_label}",
        )

    hits.sort(key=lambda h: (h["order"], h["center_mhz"]))
    return _format_result(
        {
            "victim": {"band": v_label, "start_mhz": v_start, "end_mhz": v_end},
            "max_order": max_order,
            "include_harmonics": include_harmonics,
            "products_evaluated": evaluated,
            "hit_count": len(hits),
            "hits": hits,
        }
    )


async def _handle_imd_batch(args: dict[str, Any]) -> CallToolResult:
    """Enumerate harmonic + IMD hits from many carriers into one victim band."""
    max_order = int(args.get("max_order", 7))
    include_harmonics = bool(args.get("include_harmonics", True))
    profile = args.get("constraint_profile", "single_radio")
    if profile not in CONSTRAINT_PROFILES:
        profile = "single_radio"

    victim_key = args["victim"]
    v_label, v_start, v_end = _victim_band(victim_key)

    # Default carriers: every known band except the victim and GNSS (receive-only).
    victim_norm = victim_key.strip().upper().replace(" ", "_")
    carriers: list[str] = args.get("carriers") or [
        k for k in BAND_EDGES if k != victim_norm and k != "GNSS_L1"
    ]

    hits: list[dict[str, Any]] = []

    if include_harmonics:
        for c in carriers:
            label, s, e = _carrier_edges(c)
            for p in harmonic_products(s, e, max_order, "f1"):
                if p.overlaps(v_start, v_end):
                    row = p.to_dict()
                    row.update({"source": "harmonic", "carriers": label})
                    hits.append(row)

    for c1, c2 in combinations_with_replacement(carriers, 2):
        try:
            if not combination_allowed(c1, c2, victim_key, profile):
                continue
        except ValueError:
            # Custom ranges can't be constraint-checked by name; allow them.
            pass
        l1, s1, e1 = _carrier_edges(c1)
        l2, s2, e2 = _carrier_edges(c2)
        for p in intermod_products(s1, e1, s2, e2, max_order):
            if p.overlaps(v_start, v_end):
                row = p.to_dict()
                row.update({"source": "IMD", "carriers": f"{l1} + {l2}"})
                hits.append(row)

    hits.sort(key=lambda h: (h["order"], h["center_mhz"]))
    return _format_result(
        {
            "victim": {"band": v_label, "start_mhz": v_start, "end_mhz": v_end},
            "constraint_profile": profile,
            "carriers_considered": carriers,
            "max_order": max_order,
            "hit_count": len(hits),
            "hits": hits,
        }
    )


# =============================================================================
# Registration
# =============================================================================

_KNOWN_BANDS = ", ".join(sorted(BAND_EDGES))

registry.register(
    Tool(
        name="cmw_imd_analyze",
        description=(
            "Compute harmonic and intermodulation products from one or two "
            "aggressor carriers and report which fall into a victim receive band. "
            "Pure calculation - no instrument needed. Use before a coex sweep to "
            "pick aggressor bands/frequencies worth testing."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "carrier1": {
                    "type": "string",
                    "description": (
                        "First aggressor: a band key or a 'start-end' MHz range. "
                        f"Known bands: {_KNOWN_BANDS}"
                    ),
                },
                "carrier2": {
                    "type": "string",
                    "description": "Optional second aggressor (band key or 'start-end' MHz).",
                },
                "victim": {
                    "type": "string",
                    "description": "Victim receiver band key or 'start-end' MHz range.",
                },
                "max_order": {
                    "type": "integer",
                    "description": "Highest IMD/harmonic order to evaluate (default 7).",
                    "default": 7,
                },
                "include_harmonics": {
                    "type": "boolean",
                    "description": "Also evaluate single-carrier harmonics (default true).",
                    "default": True,
                },
            },
            "required": ["carrier1", "victim"],
        },
    ),
    _handle_imd_analyze,
)

registry.register(
    Tool(
        name="cmw_imd_batch",
        description=(
            "Batch coexistence scan: enumerate harmonic + intermodulation hits "
            "from many aggressor carriers into a single victim band, applying "
            "physical-radio constraint rules. Pure calculation - no instrument."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "victim": {
                    "type": "string",
                    "description": f"Victim band key or 'start-end' MHz. Known: {_KNOWN_BANDS}",
                },
                "carriers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Aggressor band keys to consider. Default: all known bands "
                        "except the victim and GNSS (receive-only)."
                    ),
                },
                "constraint_profile": {
                    "type": "string",
                    "enum": list(CONSTRAINT_PROFILES.keys()),
                    "description": (
                        "'single_radio' applies shared-front-end rules; 'none' "
                        "enumerates every combination (default single_radio)."
                    ),
                    "default": "single_radio",
                },
                "max_order": {
                    "type": "integer",
                    "description": "Highest IMD/harmonic order (default 7).",
                    "default": 7,
                },
                "include_harmonics": {
                    "type": "boolean",
                    "description": "Also evaluate single-carrier harmonics (default true).",
                    "default": True,
                },
            },
            "required": ["victim"],
        },
    ),
    _handle_imd_batch,
)

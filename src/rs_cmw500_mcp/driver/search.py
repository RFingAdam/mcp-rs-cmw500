"""Hardware-agnostic coarse+fine threshold search.

Both LTE receiver sensitivity (BLER vs RS-EPRE level) and BLE receiver
sensitivity (PER vs CMW TX level) reduce to the same problem: find the lowest
stimulus *level* at which an error metric stays below a target percentage. This
module implements that search once, driven by an injected async ``measure``
callable, so it is fully testable without an instrument.

Convention: a *lower* level is harder for the DUT (higher error). "Sensitivity"
is the lowest level whose metric is still below the target (the last passing
level). ``measure(level)`` returns the metric percent, or ``None`` to signal a
link/attach failure that should abort the search.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

Measure = Callable[[float], Awaitable[float | None]]
Hook = Callable[[], Awaitable[Any]]


@dataclass
class SearchPoint:
    """One measured (level, metric) sample in a search trace."""

    level: float
    metric: float | None

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "metric": self.metric}


@dataclass
class ThresholdSearchResult:
    """Outcome of a :func:`descend_to_threshold` search.

    status:
        ``"ok"``       - a threshold was found.
        ``"no_pass"``  - the metric never dropped below the target.
        ``"drop"``     - a link/attach failure aborted the search.
    threshold_level: lowest level with metric < target (the sensitivity), or None.
    """

    status: str
    threshold_level: float | None
    trace: list[SearchPoint] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "threshold_level": self.threshold_level,
            "points": len(self.trace),
            "trace": [p.to_dict() for p in self.trace],
        }


async def descend_to_threshold(
    measure: Measure,
    start_level: float,
    coarse_step: float,
    fine_step: float,
    target_pct: float = 10.0,
    level_floor: float | None = None,
    level_ceiling: float | None = None,
    ascend_first: bool = False,
    on_coarse_start: Hook | None = None,
    on_fine_start: Hook | None = None,
) -> ThresholdSearchResult:
    """Coarse-then-fine downward search for the sensitivity level.

    Args:
        measure: async ``(level) -> metric_pct | None`` (None aborts as "drop").
        start_level: initial level.
        coarse_step: coarse descent step (positive).
        fine_step: fine descent step (positive).
        target_pct: error-metric threshold (default 10%).
        level_floor: lowest level to probe (search stops instead of going below).
        level_ceiling: highest level to probe when ``ascend_first`` climbs.
        ascend_first: if the start level is too low to pass, climb by ``coarse_step``
            until a passing level is found before descending (LTE EBL uses this;
            BLE starts from a known-good level and does not).
        on_coarse_start / on_fine_start: optional async hooks fired once before the
            coarse and fine phases (e.g. LTE switches 100 -> 500 measured subframes).

    Returns:
        ThresholdSearchResult.
    """
    if coarse_step <= 0 or fine_step <= 0:
        raise ValueError("coarse_step and fine_step must be positive")

    trace: list[SearchPoint] = []

    async def probe(level: float) -> float | None:
        value = await measure(level)
        trace.append(SearchPoint(level, value))
        return value

    if on_coarse_start is not None:
        await on_coarse_start()

    level = start_level

    # Optional ascent to a first passing level.
    if ascend_first:
        value = await probe(level)
        if value is None:
            return ThresholdSearchResult("drop", None, trace)
        while value >= target_pct:
            if level_ceiling is not None and level >= level_ceiling:
                return ThresholdSearchResult("no_pass", None, trace)
            level = round(level + coarse_step, 4)
            value = await probe(level)
            if value is None:
                return ThresholdSearchResult("drop", None, trace)

    # Coarse descent: step down until the metric fails.
    last_passing: float | None = None
    while True:
        value = await probe(level)
        if value is None:
            return ThresholdSearchResult("drop", None, trace)
        if value >= target_pct:
            break
        last_passing = level
        next_level = round(level - coarse_step, 4)
        if level_floor is not None and next_level < level_floor:
            break
        level = next_level

    if last_passing is None:
        return ThresholdSearchResult("no_pass", None, trace)

    # Fine descent from the last coarse-passing level.
    if on_fine_start is not None:
        await on_fine_start()

    level = last_passing
    threshold = last_passing
    while True:
        next_level = round(level - fine_step, 4)
        if level_floor is not None and next_level < level_floor:
            break
        level = next_level
        value = await probe(level)
        if value is None:
            # Link dropped mid-refine; keep the best confirmed level.
            return ThresholdSearchResult("ok", threshold, trace)
        if value >= target_pct:
            break
        threshold = level

    return ThresholdSearchResult("ok", threshold, trace)

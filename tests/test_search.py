"""Tests for the coarse+fine threshold search primitive (no hardware)."""

import pytest

from rs_cmw500_mcp.driver.search import descend_to_threshold


def _step_curve(threshold: float, pass_pct: float = 5.0, fail_pct: float = 50.0):
    """Synthetic DUT: passes (low metric) while level >= threshold."""

    async def measure(level: float) -> float:
        return pass_pct if level >= threshold else fail_pct

    return measure


class TestDescendToThreshold:
    @pytest.mark.asyncio
    async def test_ble_style_descend(self):
        # Start from a good level, descend to find the crossing.
        res = await descend_to_threshold(
            _step_curve(-72.0), start_level=-50, coarse_step=5, fine_step=1
        )
        assert res.status == "ok"
        assert res.threshold_level == -72.0

    @pytest.mark.asyncio
    async def test_lte_style_ascend_then_descend(self):
        # Start too low; must climb to a passing level first.
        res = await descend_to_threshold(
            _step_curve(-92.0),
            start_level=-110,
            coarse_step=5,
            fine_step=1,
            ascend_first=True,
            level_ceiling=-50,
            level_floor=-125,
        )
        assert res.status == "ok"
        assert res.threshold_level == -92.0

    @pytest.mark.asyncio
    async def test_no_pass_when_ceiling_never_passes(self):
        async def always_fail(level: float) -> float:
            return 50.0

        res = await descend_to_threshold(
            always_fail,
            start_level=-110,
            coarse_step=5,
            fine_step=1,
            ascend_first=True,
            level_ceiling=-50,
        )
        assert res.status == "no_pass"
        assert res.threshold_level is None

    @pytest.mark.asyncio
    async def test_drop_aborts(self):
        async def drops(level: float) -> float | None:
            return None

        res = await descend_to_threshold(drops, start_level=-50, coarse_step=5, fine_step=1)
        assert res.status == "drop"

    @pytest.mark.asyncio
    async def test_phase_hooks_fire_once(self):
        calls = {"coarse": 0, "fine": 0}

        async def on_coarse() -> None:
            calls["coarse"] += 1

        async def on_fine() -> None:
            calls["fine"] += 1

        await descend_to_threshold(
            _step_curve(-72.0),
            start_level=-50,
            coarse_step=5,
            fine_step=1,
            on_coarse_start=on_coarse,
            on_fine_start=on_fine,
        )
        assert calls == {"coarse": 1, "fine": 1}

    @pytest.mark.asyncio
    async def test_trace_records_every_probe(self):
        res = await descend_to_threshold(
            _step_curve(-72.0), start_level=-50, coarse_step=5, fine_step=1
        )
        assert res.trace  # non-empty
        assert res.trace[0].level == -50

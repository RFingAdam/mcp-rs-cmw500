"""Tests for coex routing validation, plan expansion, and the sweep engine."""

import json

import pytest

from rs_cmw500_mcp.coex.orchestrator import (
    AggressorCondition,
    CoexSweep,
    SweepPlan,
    VictimSpec,
    build_lte_ble_plan,
)
from rs_cmw500_mcp.coex.routing import RoutingError, validate_routing
from rs_cmw500_mcp.tools import handle_tool
from tests.mock_scpi import make_mock_driver


class TestRouting:
    def test_distinct_ok(self):
        validate_routing({"lte": "RF1COM", "ble": "RF2COM"})  # no raise

    def test_shared_connector_raises(self):
        with pytest.raises(RoutingError):
            validate_routing({"lte": "RF1COM", "ble": "rf1com"})

    def test_blank_raises(self):
        with pytest.raises(RoutingError):
            validate_routing({"lte": ""})


class TestPlanExpansion:
    def test_build_lte_ble_plan(self):
        victim = VictimSpec(channel_start=1, channel_end=3, channel_spacing=1)
        plan = build_lte_ble_plan([7], earfcn_spacing=350, victim=victim, include_baseline=True)
        # 1 baseline + 3 EARFCNs (2775, 3125, 3424) = 4 conditions; 3 channels.
        assert len(plan.conditions) == 4
        assert plan.conditions[0].technology == "NONE"
        assert plan.channels == [1, 2, 3]
        assert plan.total_points == 12

    def test_plan_without_baseline(self):
        victim = VictimSpec(channel_start=1, channel_end=1)
        plan = build_lte_ble_plan([7], 10000, victim, include_baseline=False)
        assert all(c.technology == "LTE" for c in plan.conditions)


def _per_curve(sock, threshold_dbm=-70.0):
    def per_response(_cmd: str) -> str:
        level = None
        for c in reversed(sock.writes):
            if "RFS:LEV" in c:
                level = float(c.rsplit(" ", 1)[1])
                break
        per = 2 if (level is not None and level >= threshold_dbm) else 50
        return f"0,{per},900,1000"

    return per_response


class TestCoexSweep:
    @pytest.mark.asyncio
    async def test_baseline_plus_lte_condition(self):
        victim = VictimSpec(channel_start=1, channel_end=1, channel_spacing=1, packets=50)
        plan = SweepPlan(
            conditions=[
                AggressorCondition("BASELINE", "NONE"),
                AggressorCondition("LTE_B7_CH3100", "LTE", 7, 3100, 2655.0, 2535.0),
            ],
            victim=victim,
        )
        sweep = CoexSweep("t1", plan, "mock", 5025)
        cmw = make_mock_driver({"PSW:STAT?": "ATT"})
        cmw._scpi.responses["PER:NMOD"] = _per_curve(cmw._scpi)

        result = await sweep.step(cmw, max_points=plan.total_points)

        assert sweep.done is True
        assert result["status"] == "complete"  # all points consumed
        assert "long" not in result  # step() omits long-format rows
        full = sweep.result()
        assert full["status"] == "complete"
        rows = full["matrix"]["rows"]
        assert [r["label"] for r in rows] == ["BASELINE", "LTE_B7_CH3100"]
        assert rows[0]["cells"]["1"] == -70.0
        assert rows[1]["cells"]["1"] == -70.0
        # LTE aggressor was actually applied.
        assert "CONFigure:LTE:SIGN1:BAND OB7" in cmw._scpi.writes
        assert any("PCC:CHANnel:DL 3100" in w for w in cmw._scpi.writes)


class TestCoexTools:
    @pytest.mark.asyncio
    async def test_plan_tool_returns_sweep_id(self):
        res = await handle_tool(
            "cmw_coex_plan",
            {"lte_bands": [7], "earfcn_spacing": 350, "ble_channel_start": 1, "ble_channel_end": 2},
        )
        data = json.loads(res.content[0].text)
        assert "sweep_id" in data
        assert data["total_points"] > 0

    @pytest.mark.asyncio
    async def test_validate_routing_tool(self):
        ok = await handle_tool(
            "cmw_coex_validate_routing", {"connectors": {"lte": "RF1", "ble": "RF2"}}
        )
        assert ok.isError is False
        bad = await handle_tool(
            "cmw_coex_validate_routing", {"connectors": {"lte": "RF1", "ble": "RF1"}}
        )
        assert bad.isError is True

    @pytest.mark.asyncio
    async def test_empty_plan_is_error(self):
        res = await handle_tool("cmw_coex_plan", {"lte_bands": [], "include_baseline": False})
        assert res.isError is True

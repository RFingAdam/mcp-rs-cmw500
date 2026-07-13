"""Tests for the coexistence / IMD planner MCP tools (pure computation)."""

import json

import pytest

from rs_cmw500_mcp.tools import handle_tool  # triggers tool registration


async def dispatch(name, args):
    """Use the production dispatch path (wraps exceptions as isError results)."""
    return await handle_tool(name, args)


def _payload(result):
    assert result.isError is False
    return json.loads(result.content[0].text)


class TestImdAnalyze:
    @pytest.mark.asyncio
    async def test_two_carrier_sum_hit(self):
        res = await dispatch(
            "cmw_imd_analyze",
            {
                "carrier1": "700-700",
                "carrier2": "875-875",
                "victim": "1570-1580",
                "include_harmonics": False,
            },
        )
        data = _payload(res)
        assert data["hit_count"] >= 1
        centers = [h["center_mhz"] for h in data["hits"]]
        assert 1575.0 in centers  # 700 + 875
        assert all(h["source"] == "IMD" for h in data["hits"])

    @pytest.mark.asyncio
    async def test_harmonic_hit_named_band(self):
        # LTE B8 UL 880-915 -> 2nd harmonic 1760-1830 overlaps 1800-1810.
        res = await dispatch(
            "cmw_imd_analyze",
            {"carrier1": "LTE_B8", "victim": "1800-1810", "include_harmonics": True},
        )
        data = _payload(res)
        assert any(h["source"] == "harmonic" and h["order"] == 2 for h in data["hits"])

    @pytest.mark.asyncio
    async def test_no_hit_returns_empty(self):
        res = await dispatch(
            "cmw_imd_analyze",
            {"carrier1": "900-901", "victim": "5000-5001", "include_harmonics": True},
        )
        data = _payload(res)
        assert data["hit_count"] == 0
        assert data["hits"] == []

    @pytest.mark.asyncio
    async def test_unknown_band_is_error(self):
        res = await dispatch("cmw_imd_analyze", {"carrier1": "NOPE", "victim": "GNSS_L1"})
        assert res.isError is True


class TestImdBatch:
    @pytest.mark.asyncio
    async def test_batch_excludes_gnss_and_victim_from_carriers(self):
        res = await dispatch(
            "cmw_imd_batch", {"victim": "GNSS_L1", "constraint_profile": "single_radio"}
        )
        data = _payload(res)
        assert "GNSS_L1" not in data["carriers_considered"]
        assert data["constraint_profile"] == "single_radio"
        assert isinstance(data["hits"], list)

    @pytest.mark.asyncio
    async def test_batch_hits_sorted_by_order(self):
        res = await dispatch("cmw_imd_batch", {"victim": "GNSS_L1", "max_order": 5})
        data = _payload(res)
        orders = [h["order"] for h in data["hits"]]
        assert orders == sorted(orders)

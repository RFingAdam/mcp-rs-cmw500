"""Tests for the GPRF spectrum trigger/fetch (de-stubbed)."""

import pytest

from tests.mock_scpi import make_mock_driver


class TestSpectrum:
    @pytest.mark.asyncio
    async def test_trigger_emits_init(self):
        cmw = make_mock_driver()
        await cmw.meas_trigger_spectrum()
        assert cmw._scpi.writes[-1] == "INITiate:GPRF:MEASurement1:SPECtrum"

    @pytest.mark.asyncio
    async def test_fetch_parses_trace(self):
        cmw = make_mock_driver({"FETCh:GPRF:MEASurement1:SPECtrum:AVERage?": "0,-80.1,-79.5,-81.2"})
        result = await cmw.meas_fetch_spectrum("AVERage")
        assert result["reliability"] == "0"
        assert result["statistic"] == "AVERage"
        assert result["power_dbm"] == [-80.1, -79.5, -81.2]
        assert result["point_count"] == 3
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_fetch_statistic_selects_node(self):
        cmw = make_mock_driver({"SPECtrum:MAXimum?": "0,-70.0"})
        result = await cmw.meas_fetch_spectrum("maximum")
        assert result["statistic"] == "MAXimum"
        assert result["power_dbm"] == [-70.0]

    @pytest.mark.asyncio
    async def test_no_longer_returns_stub(self):
        cmw = make_mock_driver({"SPECtrum:AVERage?": "0,-90.0"})
        result = await cmw.meas_fetch_spectrum()
        assert "not yet configured" not in str(result)

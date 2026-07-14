"""Tests for licensing map + bench self-test (Phase D), hardware-free."""

import json

import pytest

from rs_cmw500_mcp.licensing import domains_for_options
from rs_cmw500_mcp.profile import clear_active_profile
from rs_cmw500_mcp.tools import selftest
from tests.mock_scpi import make_mock_driver


@pytest.fixture(autouse=True)
def _clear_profile():
    clear_active_profile()
    yield
    clear_active_profile()


class TestLicensing:
    def test_domains_for_options(self):
        d = domains_for_options(["CMW-KS200", "CMW-KS650", "CMW-B450A"])
        assert d["gsm_signaling"] is True
        assert d["wlan_signaling"] is True
        assert d["wlan_throughput"] is True
        assert d["lte_signaling"] is False

    def test_empty_options(self):
        d = domains_for_options([])
        assert all(v is False for v in d.values())


class TestSelftest:
    @pytest.mark.asyncio
    async def test_selftest_readonly(self, monkeypatch):
        cmw = make_mock_driver(
            {
                "*IDN?": "Rohde&Schwarz,CMW500,123456,V3.8.10",
                "SYSTem:BASE:OPTion:LIST?": "CMW-KS200,CMW-KS650",
            }
        )

        async def fake_get_cmw(host=None, port=None):
            return cmw

        monkeypatch.setattr(selftest, "_get_cmw", fake_get_cmw)
        res = await selftest._handle_selftest({"run_smoke": True})
        data = json.loads(res.content[0].text)

        assert data["instrument"]["model"] == "CMW500"
        assert data["domains"]["gsm_signaling"]["licensed"] is True
        assert data["domains"]["wlan_signaling"]["licensed"] is True
        assert data["domains"]["lte_signaling"]["licensed"] is False
        # Licensed + probed domains report a smoke result.
        assert data["domains"]["gsm_signaling"]["smoke_ok"] is True
        # Non-destructive: nothing switched on.
        assert not any("STATe ON" in w for w in cmw._scpi.writes)
        assert not any("GENerator1:STATe ON" in w for w in cmw._scpi.writes)

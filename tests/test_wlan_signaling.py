"""Tests for WLAN signaling (AP emulation) driver methods and tools."""

import json

import pytest

from rs_cmw500_mcp.tools import wlan_signaling
from tests.mock_scpi import make_mock_driver


class TestWlanSignalingSCPI:
    @pytest.mark.asyncio
    async def test_ap_state(self):
        cmw = make_mock_driver()
        await cmw.wlan_sig_set_state(True)
        assert cmw._scpi.writes[-1] == "SOURce:WLAN:SIGN1:STATe ON"
        await cmw.wlan_sig_set_state(False)
        assert cmw._scpi.writes[-1] == "SOURce:WLAN:SIGN1:STATe OFF"

    @pytest.mark.asyncio
    async def test_configure_fields(self):
        cmw = make_mock_driver()
        await cmw.wlan_sig_set_standard("HEOFdm")
        await cmw.wlan_sig_set_bandwidth("BW80")
        await cmw.wlan_sig_set_ssid("TestAP")
        assert "CONFigure:WLAN:SIGN1:STANdard HEOFdm" in cmw._scpi.writes
        assert "CONFigure:WLAN:SIGN1:RFSettings:BWIDth BW80" in cmw._scpi.writes
        assert "CONFigure:WLAN:SIGN1:CONNection:SSID 'TestAP'" in cmw._scpi.writes

    @pytest.mark.asyncio
    async def test_ssid_injection_rejected(self):
        cmw = make_mock_driver()
        with pytest.raises(ValueError):
            await cmw.wlan_sig_set_ssid("evil;*RST")


class TestWlanSignalingTools:
    @pytest.mark.asyncio
    async def test_configure_ap_dispatch(self, monkeypatch):
        cmw = make_mock_driver()

        async def fake_get_cmw(host=None, port=None):
            return cmw

        monkeypatch.setattr(wlan_signaling, "_get_cmw", fake_get_cmw)
        res = await wlan_signaling._handle_wlan_sig_configure_ap(
            {"standard": "VHTofdm", "bandwidth": "BW40", "channel": 36, "ssid": "CoexAP"}
        )
        data = json.loads(res.content[0].text)
        assert data["status"] == "ok"
        assert "CONFigure:WLAN:SIGN1:RFSettings:CHANnel 36" in cmw._scpi.writes
        assert "CONFigure:WLAN:SIGN1:CONNection:SSID 'CoexAP'" in cmw._scpi.writes

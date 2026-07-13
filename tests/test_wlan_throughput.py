"""Tests for WLAN throughput / DAU driver methods and tools."""

import json

import pytest

from rs_cmw500_mcp.tools import wlan_throughput
from tests.mock_scpi import make_mock_driver


class TestThroughput:
    @pytest.mark.asyncio
    async def test_fetch_dl_parses_bps(self):
        cmw = make_mock_driver({"THRoughput:OVERall:DLINk?": "0,1.2e7,1.0e7,1.5e7,1.25e7"})
        r = await cmw.data_throughput_fetch("DL")
        assert r.reliability == "0" and r.valid is True
        assert r.direction == "DL"
        assert r.current_bps == 1.2e7
        assert r.average_bps == 1.25e7
        d = r.to_dict()
        assert d["average_mbps"] == 12.5

    @pytest.mark.asyncio
    async def test_fetch_ul_uses_ulink_node(self):
        cmw = make_mock_driver({"THRoughput:OVERall:ULINk?": "0,5e6,4e6,6e6,5e6"})
        r = await cmw.data_throughput_fetch("UL")
        assert r.direction == "UL"
        assert r.average_bps == 5e6

    @pytest.mark.asyncio
    async def test_init(self):
        cmw = make_mock_driver()
        await cmw.data_throughput_init()
        assert cmw._scpi.writes[-1] == "INITiate:DATA:MEASurement1:THRoughput"


class TestIperfPing:
    @pytest.mark.asyncio
    async def test_iperf_configure_and_init(self):
        cmw = make_mock_driver()
        await cmw.data_iperf_configure(protocol="UDP", duration_s=5, parallel=2)
        assert "CONFigure:DATA:MEASurement1:IPERf:PROTocol UDP" in cmw._scpi.writes
        assert "CONFigure:DATA:MEASurement1:IPERf:TDURation 5" in cmw._scpi.writes
        await cmw.data_iperf_init()
        assert cmw._scpi.writes[-1] == "INITiate:DATA:MEASurement1:IPERf"

    @pytest.mark.asyncio
    async def test_ping(self):
        cmw = make_mock_driver({"PING:ALL?": "0,10,0,12.5"})
        result = await cmw.data_ping("192.168.0.1", count=10)
        assert result["reliability"] == "0"
        assert "CONFigure:DATA:MEASurement1:PING:DADDress '192.168.0.1'" in cmw._scpi.writes

    @pytest.mark.asyncio
    async def test_ping_injection_rejected(self):
        cmw = make_mock_driver()
        with pytest.raises(ValueError):
            await cmw.data_ping("1.2.3.4;*RST")


class TestTools:
    @pytest.mark.asyncio
    async def test_throughput_tool(self, monkeypatch):
        cmw = make_mock_driver({"THRoughput:OVERall:DLINk?": "0,2e7,1e7,3e7,2e7"})

        async def fake_get_cmw(host=None, port=None):
            return cmw

        monkeypatch.setattr(wlan_throughput, "_get_cmw", fake_get_cmw)
        res = await wlan_throughput._handle_data_throughput({"direction": "DL", "settle_s": 0})
        data = json.loads(res.content[0].text)
        assert data["valid"] is True
        assert data["average_mbps"] == 20.0

"""Tests for LTE RX / Extended-BLER driver methods and sensitivity search."""

import json

import pytest

from rs_cmw500_mcp.models.cmw_types import LTEBandwidth
from rs_cmw500_mcp.tools import lte_rx
from rs_cmw500_mcp.tools.lte_rx import run_lte_rx_sensitivity, wait_for_lte_attach
from tests.mock_scpi import make_mock_driver


class TestLteRxDriverSCPI:
    @pytest.mark.asyncio
    async def test_operating_band(self):
        cmw = make_mock_driver()
        await cmw.lte_set_operating_band(7)
        assert cmw._scpi.writes[-1] == "CONFigure:LTE:SIGN1:BAND OB7"

    @pytest.mark.asyncio
    async def test_rx_bandwidth_pcc_dl(self):
        cmw = make_mock_driver()
        await cmw.lte_set_rx_bandwidth(LTEBandwidth.BW5)
        assert cmw._scpi.writes[-1] == "CONFigure:LTE:SIGN1:CELL:BANDwidth:PCC:DL B050"

    @pytest.mark.asyncio
    async def test_set_earfcn_direction(self):
        cmw = make_mock_driver()
        await cmw.lte_set_earfcn(3100, "DL")
        assert cmw._scpi.writes[-1] == "CONFigure:LTE:SIGN1:RFSettings:PCC:CHANnel:DL 3100"
        with pytest.raises(ValueError):
            await cmw.lte_set_earfcn(3100, "XX")

    @pytest.mark.asyncio
    async def test_rsepre_level(self):
        cmw = make_mock_driver()
        await cmw.lte_set_rsepre_level(-90.0)
        assert cmw._scpi.writes[-1] == "CONFigure:LTE:SIGN1:DL:PCC:RSEP:LEV -90.0"

    @pytest.mark.asyncio
    async def test_ebl_configure(self):
        cmw = make_mock_driver()
        await cmw.lte_ebl_configure(100, single_shot=True)
        assert "CONFigure:LTE:SIGN1:EBL:REP SING" in cmw._scpi.writes
        assert "CONFigure:LTE:SIGN1:EBL:SFR 100" in cmw._scpi.writes

    @pytest.mark.asyncio
    async def test_ebl_init(self):
        cmw = make_mock_driver()
        await cmw.lte_ebl_init()
        assert cmw._scpi.writes[-1] == "INITiate:LTE:SIGN1:EBL"

    @pytest.mark.asyncio
    async def test_ebl_fetch_parses_bler(self):
        cmw = make_mock_driver({"EBL:PCC:REL?": "0,1,1,7,100"})
        result = await cmw.lte_ebl_fetch()
        assert result.reliability == "0"
        assert result.bler_percent == 7.0
        assert result.dropped is False

    @pytest.mark.asyncio
    async def test_ebl_fetch_detects_drop(self):
        cmw = make_mock_driver({"EBL:PCC:REL?": "19,0,0,0,0"})
        result = await cmw.lte_ebl_fetch()
        assert result.dropped is True
        assert result.bler_percent is None


class TestAttachLifecycle:
    @pytest.mark.asyncio
    async def test_attach_success(self):
        cmw = make_mock_driver({"CELL:STAT:ALL?": "ON,ADJ", "PSW:STAT?": "ATT"})
        attached, state = await wait_for_lte_attach(cmw, timeout_s=5, adj_timeout_s=5)
        assert attached is True
        assert state == "ATT"
        assert "SOURce:LTE:SIGN1:CELL:STAT ON" in cmw._scpi.writes


class TestSensitivitySearch:
    @pytest.mark.asyncio
    async def test_sensitivity_against_synthetic_dut(self):
        cmw = make_mock_driver()
        sock = cmw._scpi

        def ebl_response(_cmd: str) -> str:
            # Synthetic DUT: BLER passes (3%) while RS-EPRE >= -92 dBm.
            level = None
            for c in reversed(sock.writes):
                if "RSEP:LEV" in c:
                    level = float(c.rsplit(" ", 1)[1])
                    break
            bler = 3 if (level is not None and level >= -92) else 50
            return f"0,1,1,{bler},100"

        sock.responses["EBL:PCC:REL?"] = ebl_response

        result = await run_lte_rx_sensitivity(
            cmw,
            earfcn=3100,
            start_level=-110,
            coarse_step=5,
            fine_step=1,
            coarse_delay_s=0.0,
            fine_delay_s=0.0,
        )
        assert result.status == "ok"
        assert result.sensitivity_dbm == -92.0
        assert result.frequency_mhz == 2655.0  # band 7 EARFCN 3100
        assert result.technology == "LTE-BLER"


class TestToolRegistration:
    @pytest.mark.asyncio
    async def test_measure_bler_tool_dispatch(self, monkeypatch):
        cmw = make_mock_driver({"EBL:PCC:REL?": "0,1,1,4,100"})

        async def fake_get_cmw(host=None, port=None):
            return cmw

        monkeypatch.setattr(lte_rx, "_get_cmw", fake_get_cmw)
        res = await lte_rx._handle_lte_rx_measure_bler({"level_dbm": -80, "delay_s": 0})
        data = json.loads(res.content[0].text)
        assert data["bler_percent"] == 4.0
        assert data["level_dbm"] == -80

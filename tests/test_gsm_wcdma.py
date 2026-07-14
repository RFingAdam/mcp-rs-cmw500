"""Tests for GSM and WCDMA signaling driver methods (C2/C3)."""

import pytest

from tests.mock_scpi import make_mock_driver


class TestGsm:
    @pytest.mark.asyncio
    async def test_cell_state(self):
        cmw = make_mock_driver()
        await cmw.gsm_sig_set_state(True)
        assert cmw._scpi.writes[-1] == "SOURce:GSM:SIGN1:STATe ON"

    @pytest.mark.asyncio
    async def test_configure_fields(self):
        cmw = make_mock_driver()
        await cmw.gsm_sig_set_band("G09")
        await cmw.gsm_sig_set_arfcn(62, "TCH")
        assert "CONFigure:GSM:SIGN1:BAND G09" in cmw._scpi.writes
        assert "CONFigure:GSM:SIGN1:RFSettings:CHANnel:TCH 62" in cmw._scpi.writes
        with pytest.raises(ValueError):
            await cmw.gsm_sig_set_arfcn(1, "XX")

    @pytest.mark.asyncio
    async def test_ber_parse(self):
        cmw = make_mock_driver({"FETCh:GSM:SIGN1:BER?": "0,1.5,100"})
        r = await cmw.gsm_sig_fetch_ber()
        assert r.reliability == "0"
        assert r.ber == 1.5

    @pytest.mark.asyncio
    async def test_meas_power(self):
        cmw = make_mock_driver({"GSM:MEAS1:MEValuation:POWer:CURRent?": "0,33.0,32.5"})
        await cmw.gsm_meas_init()
        r = await cmw.gsm_meas_fetch_power()
        assert r.current_dbm == 33.0


class TestWcdma:
    @pytest.mark.asyncio
    async def test_cell_state(self):
        cmw = make_mock_driver()
        await cmw.wcdma_sig_set_state(True)
        assert cmw._scpi.writes[-1] == "SOURce:WCDMa:SIGN1:CELL:STATe ON"

    @pytest.mark.asyncio
    async def test_configure_fields(self):
        cmw = make_mock_driver()
        await cmw.wcdma_sig_set_band("OB1")
        await cmw.wcdma_sig_set_dl_channel(10700)
        assert "CONFigure:WCDMa:SIGN1:CARRier:BAND OB1" in cmw._scpi.writes
        assert "CONFigure:WCDMa:SIGN1:CARRier:DL:CHANnel 10700" in cmw._scpi.writes

    @pytest.mark.asyncio
    async def test_ber_parse(self):
        cmw = make_mock_driver({"FETCh:WCDMa:SIGN1:BER?": "0,0.2,1000"})
        r = await cmw.wcdma_sig_fetch_ber()
        assert r.reliability == "0"
        assert r.ber == 0.2

    @pytest.mark.asyncio
    async def test_connection_state_query(self):
        cmw = make_mock_driver({"SENSe:WCDMa:SIGN1:CONNection:STATe?": "CEST"})
        assert (await cmw.wcdma_sig_connection_state()).strip() == "CEST"

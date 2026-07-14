"""Tests for BLE signaling PER driver methods and sensitivity search."""

import pytest

from rs_cmw500_mcp.tools.bluetooth_signaling import (
    measure_ble_per,
    run_ble_rx_sensitivity,
)
from tests.mock_scpi import make_mock_driver


class TestBleSignalingSCPI:
    @pytest.mark.asyncio
    async def test_set_packets(self):
        cmw = make_mock_driver()
        await cmw.ble_sig_set_packets(100)
        assert cmw._scpi.writes[-1] == "CONFigure:BLUetooth:SIGN1:RXQ:PACK:NMOD:LEN:LE1M 100"

    @pytest.mark.asyncio
    async def test_set_channel(self):
        cmw = make_mock_driver()
        await cmw.ble_sig_set_channel(5)
        assert cmw._scpi.writes[-1] == "CONFigure:BLUetooth:SIGN1:RFS:NMOD:MCH:LEN 5"

    @pytest.mark.asyncio
    async def test_set_level(self):
        cmw = make_mock_driver()
        await cmw.ble_sig_set_level(-40.0)
        assert cmw._scpi.writes[-1] == "CONFigure:BLUetooth:SIGN1:RFS:LEV -40.0"

    @pytest.mark.asyncio
    async def test_read_per_valid(self):
        cmw = make_mock_driver({"PER:NMOD": "0,3.5,900,1000"})
        result = await cmw.ble_sig_read_per()
        assert result.reliability == "0"
        assert result.per_percent == 3.5
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_read_per_invalid_reliability(self):
        cmw = make_mock_driver({"PER:NMOD": "1,0,0,0"})
        result = await cmw.ble_sig_read_per()
        assert result.valid is False
        assert result.per_percent is None

    @pytest.mark.asyncio
    async def test_connection_action(self):
        cmw = make_mock_driver()
        await cmw.ble_sig_connection("CONN")
        assert cmw._scpi.writes[-1] == "CALL:BLUetooth:SIGN1:CONN:ACT:LES CONN"
        await cmw.ble_sig_connection("det")
        assert cmw._scpi.writes[-1] == "CALL:BLUetooth:SIGN1:CONN:ACT:LES DET"
        with pytest.raises(ValueError):
            await cmw.ble_sig_connection("nope")

    @pytest.mark.asyncio
    async def test_clear(self):
        cmw = make_mock_driver()
        await cmw.ble_sig_clear()
        assert cmw._scpi.writes[-1] == "*CLS"


class TestMeasureBlePer:
    @pytest.mark.asyncio
    async def test_measure_returns_none_on_drop(self):
        cmw = make_mock_driver({"PER:NMOD": "1,0,0,0"})
        assert await measure_ble_per(cmw, -50.0, settle_s=0.0) is None


class TestBleSensitivitySearch:
    @pytest.mark.asyncio
    async def test_sensitivity_against_synthetic_dut(self):
        cmw = make_mock_driver()
        sock = cmw._scpi

        def per_response(_cmd: str) -> str:
            level = None
            for c in reversed(sock.writes):
                if "RFS:LEV" in c:
                    level = float(c.rsplit(" ", 1)[1])
                    break
            per = 2 if (level is not None and level >= -75) else 50
            return f"0,{per},900,1000"

        sock.responses["PER:NMOD"] = per_response

        result = await run_ble_rx_sensitivity(
            cmw,
            channel=10,
            start_power_dbm=-50,
            coarse_step=5,
            fine_step=1,
            settle_s=0.0,
        )
        assert result.status == "ok"
        assert result.sensitivity_dbm == -75.0
        assert result.technology == "BLE-PER"
        assert result.frequency_mhz == 2422.0  # 2402 + 2*10

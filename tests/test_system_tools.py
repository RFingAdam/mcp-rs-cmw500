"""Tests for system tools (error queue, OPC-synced raw SCPI)."""

import json

import pytest

from rs_cmw500_mcp.tools import system
from tests.mock_scpi import make_mock_driver


class TestScpiSendOpc:
    @pytest.mark.asyncio
    async def test_driver_send_opc(self):
        cmw = make_mock_driver()
        ok = await cmw.scpi_send_opc("SOURce:LTE:SIGN1:CELL:STAT ON")
        assert ok is True
        assert "SOURce:LTE:SIGN1:CELL:STAT ON" in cmw._scpi.writes
        assert "*OPC?" in cmw._scpi.commands


class TestSystemErrorTool:
    @pytest.mark.asyncio
    async def test_clean_queue(self, monkeypatch):
        cmw = make_mock_driver({"SYSTem:ERRor?": '0,"No error"'})

        async def fake_get_cmw(host=None, port=None):
            return cmw

        monkeypatch.setattr(system, "_get_cmw", fake_get_cmw)
        res = await system._handle_system_error({})
        data = json.loads(res.content[0].text)
        assert data["clean"] is True
        assert data["error_count"] == 0


class TestScpiQueryOpcGating:
    @pytest.mark.asyncio
    async def test_disabled_by_default(self):
        # Default config has allow_raw_scpi=False -> tool must refuse.
        res = await system._handle_scpi_query_opc({"command": "*RST"})
        assert res.isError is True

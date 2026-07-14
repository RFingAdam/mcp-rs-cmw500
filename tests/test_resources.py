"""Tests for MCP resources (SCPI reference + dynamic data)."""

import json

import pytest

from rs_cmw500_mcp import resources
from rs_cmw500_mcp.server import create_server


class TestResourceListing:
    def test_list_includes_core_uris(self):
        uris = {str(r.uri) for r in resources.list_resources()}
        assert "cmw://scpi/index" in uris
        assert "cmw://scpi/lte-signaling" in uris
        assert "cmw://reference/band-plan" in uris
        assert "cmw://reference/reliability-codes" in uris
        assert "cmw://capabilities" in uris


class TestResourceRead:
    @pytest.mark.asyncio
    async def test_read_static_markdown(self):
        content, mime = await resources.read_resource("cmw://scpi/lte-signaling")
        assert mime == "text/markdown"
        assert "EBL" in content and "RSEP:LEV" in content

    @pytest.mark.asyncio
    async def test_read_band_plan_json(self):
        content, mime = await resources.read_resource("cmw://reference/band-plan")
        assert mime == "application/json"
        data = json.loads(content)
        assert "7" in data["lte_fdd_bands"]
        assert "HALOW_US" in data["band_edges_mhz"]
        assert data["ble"]["advertising_channels"] == [0, 12, 39]

    @pytest.mark.asyncio
    async def test_read_band_presets_json(self):
        content, _ = await resources.read_resource("cmw://reference/band-presets")
        data = json.loads(content)
        assert "presets" in data
        assert "frequency_coverage_set" in data["presets"]

    @pytest.mark.asyncio
    async def test_capabilities_offline_is_graceful(self):
        content, mime = await resources.read_resource("cmw://capabilities")
        assert mime == "application/json"
        data = json.loads(content)
        assert "online" in data  # True or False, never raises

    @pytest.mark.asyncio
    async def test_unknown_resource_raises(self):
        with pytest.raises(ValueError):
            await resources.read_resource("cmw://nope")


def test_server_constructs_with_resources_and_prompts():
    # Smoke test: wiring resource/prompt handlers must not raise.
    server = create_server()
    assert server is not None

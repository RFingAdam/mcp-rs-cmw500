"""Tests for the per-unit bench profile (Phase A)."""

import json

import pytest

from rs_cmw500_mcp.coex.routing import RoutingError, validate_routing
from rs_cmw500_mcp.config import get_settings
from rs_cmw500_mcp.profile import (
    BenchProfile,
    apply_profile_to_settings,
    clear_active_profile,
    resolve_attenuation,
    resolve_connector,
    set_active_profile,
)
from rs_cmw500_mcp.tools import profile_tools
from tests.mock_scpi import make_mock_driver


@pytest.fixture(autouse=True)
def _clear_profile():
    clear_active_profile()
    yield
    clear_active_profile()


def _sample() -> BenchProfile:
    return BenchProfile(
        name="bench-1",
        description="lab unit",
        routing={"lte_signaling": "RF1COM", "ble_signaling": "RF2COM", "gprf_gen": "RF3COM"},
        attenuation_db={"gprf_gen": 12.5},
        expected_licenses=["KS500", "KS650"],
    )


class TestModel:
    def test_round_trip(self, tmp_path):
        p = _sample()
        path = tmp_path / "bench-1.json"
        p.save(path)
        loaded = BenchProfile.load(path)
        assert loaded.name == "bench-1"
        assert loaded.routing["ble_signaling"] == "RF2COM"
        assert loaded.attenuation_db["gprf_gen"] == 12.5
        assert loaded.to_dict() == p.to_dict()

    def test_connector_map_feeds_validate_routing(self):
        good = _sample()
        validate_routing(good.connector_map())  # distinct -> no raise
        bad = BenchProfile(name="x", routing={"lte": "RF1COM", "ble": "rf1com"})
        with pytest.raises(RoutingError):
            validate_routing(bad.connector_map())


class TestResolvers:
    def test_explicit_wins(self):
        set_active_profile(_sample())
        assert resolve_connector("lte_signaling", "RFX") == "RFX"
        assert resolve_attenuation("gprf_gen", 3.0) == 3.0

    def test_profile_fallback(self):
        set_active_profile(_sample())
        assert resolve_connector("lte_signaling", None) == "RF1COM"
        assert resolve_attenuation("gprf_gen", None) == 12.5

    def test_none_when_no_profile(self):
        assert resolve_connector("lte_signaling", None) is None
        assert resolve_attenuation("gprf_gen", None) is None


class TestApplyToSettings:
    def test_mutates_settings(self):
        p = BenchProfile(name="s")
        p.connection.host = "10.0.0.5"
        p.connection.port = 5026
        p.safety.max_generator_power_dbm = -5.0
        apply_profile_to_settings(p)
        settings = get_settings()
        assert settings.default_host == "10.0.0.5"
        assert settings.default_port == 5026
        assert settings.max_generator_power_dbm == -5.0
        # Reset so we don't leak into other tests.
        settings.default_host = "127.0.0.1"
        settings.default_port = 5025
        settings.max_generator_power_dbm = 0.0


class TestApplyTool:
    @pytest.mark.asyncio
    async def test_pushes_gprf_only(self, monkeypatch):
        set_active_profile(_sample())
        cmw = make_mock_driver()

        async def fake_get_cmw(host=None, port=None):
            return cmw

        monkeypatch.setattr(profile_tools, "_get_cmw", fake_get_cmw)
        res = await profile_tools._handle_profile_apply({})
        data = json.loads(res.content[0].text)
        assert data["status"] == "ok"
        # GPRF routing + attenuation actually sent:
        assert any("ROUTe:GPRF:GENerator1:SCENario:SPATh RF3COM" in w for w in cmw._scpi.writes)
        assert any("GENerator1:RFSettings:EATTenuation 12.5" in w for w in cmw._scpi.writes)
        # Signaling routing NOT sent (only recorded as intent):
        assert not any("SIGN" in w and "SCENario" in w for w in cmw._scpi.writes)
        assert any("lte_signaling" in line for line in data["planned_scpi"])

    @pytest.mark.asyncio
    async def test_apply_without_profile_errors(self):
        res = await profile_tools._handle_profile_apply({})
        assert res.isError is True


class TestFileTools:
    @pytest.mark.asyncio
    async def test_save_load_list(self, tmp_path):
        get_settings().profile_dir = str(tmp_path)
        saved = await profile_tools._handle_profile_save(
            {"filename": "bench-1", "profile": _sample().to_dict()}
        )
        assert json.loads(saved.content[0].text)["status"] == "ok"

        listed = json.loads((await profile_tools._handle_profile_list({})).content[0].text)
        assert listed["count"] == 1
        assert listed["profiles"][0]["name"] == "bench-1"

        loaded = json.loads(
            (await profile_tools._handle_profile_load({"filename": "bench-1"})).content[0].text
        )
        assert loaded["profile"] == "bench-1"
        assert loaded["routing_valid"] is True

"""Tests for CMW500 data models."""

import pytest

from rs_cmw500_mcp.models.cmw_types import (
    ACLRResult,
    CellConfig,
    CMW500Family,
    EVMResult,
    InstrumentInfo,
    LTEBandwidth,
    PowerResult,
    RFConfig,
    SEMResult,
    SignalPath,
    Technology,
)


class TestCMW500Family:
    """Test CMW500Family enum."""

    def test_supports_signaling(self):
        assert CMW500Family.CMW500.supports_signaling is True
        assert CMW500Family.CMW290.supports_signaling is False
        assert CMW500Family.CMW270.supports_signaling is False


class TestTechnology:
    """Test Technology enum."""

    def test_values(self):
        assert Technology.LTE_FDD.value == "LTE"
        assert Technology.GPRF.value == "GPRF"
        assert Technology.WLAN.value == "WLAN"


class TestLTEBandwidth:
    """Test LTEBandwidth enum."""

    def test_mhz_property(self):
        assert LTEBandwidth.BW1P4.mhz == 1.4
        assert LTEBandwidth.BW5.mhz == 5.0
        assert LTEBandwidth.BW10.mhz == 10.0
        assert LTEBandwidth.BW20.mhz == 20.0

    def test_from_mhz(self):
        assert LTEBandwidth.from_mhz(10.0) == LTEBandwidth.BW10
        assert LTEBandwidth.from_mhz(20.0) == LTEBandwidth.BW20
        assert LTEBandwidth.from_mhz(1.4) == LTEBandwidth.BW1P4

    def test_from_mhz_invalid(self):
        with pytest.raises(ValueError, match="Invalid LTE bandwidth"):
            LTEBandwidth.from_mhz(7.0)

    def test_scpi_values(self):
        assert LTEBandwidth.BW10.value == "B100"
        assert LTEBandwidth.BW20.value == "B200"


class TestSignalPath:
    """Test SignalPath enum."""

    def test_values(self):
        assert SignalPath.STANDALONE.value == "SALone"
        assert SignalPath.CS_PATH.value == "CSPath"


class TestInstrumentInfo:
    """Test InstrumentInfo model."""

    def test_from_idn(self):
        info = InstrumentInfo.from_idn(
            "Rohde&Schwarz,CMW500,1234567,V3.8.10"
        )
        assert info.manufacturer == "Rohde&Schwarz"
        assert info.model == "CMW500"
        assert info.serial_number == "1234567"
        assert info.firmware_version == "V3.8.10"

    def test_from_idn_partial(self):
        info = InstrumentInfo.from_idn("Rohde&Schwarz,CMW500")
        assert info.manufacturer == "Rohde&Schwarz"
        assert info.model == "CMW500"
        assert info.serial_number == ""
        assert info.firmware_version == ""

    def test_to_dict(self):
        info = InstrumentInfo(
            manufacturer="R&S",
            model="CMW500",
            serial_number="123",
            firmware_version="3.8",
            options=["K21", "K55"],
        )
        d = info.to_dict()
        assert d["manufacturer"] == "R&S"
        assert d["model"] == "CMW500"
        assert d["options"] == ["K21", "K55"]


class TestPowerResult:
    """Test PowerResult model."""

    def test_to_dict(self):
        result = PowerResult(
            current_dbm=-30.5,
            average_dbm=-30.3,
            maximum_dbm=-29.8,
            minimum_dbm=-31.0,
            reliability="OK",
        )
        d = result.to_dict()
        assert d["current_dbm"] == -30.5
        assert d["average_dbm"] == -30.3
        assert d["reliability"] == "OK"

    def test_to_dict_partial(self):
        result = PowerResult(current_dbm=-30.0)
        d = result.to_dict()
        assert "current_dbm" in d
        assert "average_dbm" not in d


class TestEVMResult:
    """Test EVMResult model."""

    def test_to_dict(self):
        result = EVMResult(evm_rms_percent=2.5, evm_peak_percent=8.1)
        d = result.to_dict()
        assert d["evm_rms_percent"] == 2.5
        assert d["evm_peak_percent"] == 8.1


class TestACLRResult:
    """Test ACLRResult model."""

    def test_to_dict(self):
        result = ACLRResult(
            aclr_minus_db=-35.0,
            aclr_plus_db=-34.5,
            aclr_minus2_db=-50.0,
            aclr_plus2_db=-49.5,
        )
        d = result.to_dict()
        assert d["aclr_minus_db"] == -35.0
        assert d["aclr_plus_db"] == -34.5


class TestSEMResult:
    """Test SEMResult model."""

    def test_to_dict_pass(self):
        result = SEMResult(passed=True, margin_db=5.2)
        d = result.to_dict()
        assert d["passed"] is True
        assert d["margin_db"] == 5.2

    def test_to_dict_fail(self):
        result = SEMResult(passed=False, margin_db=-2.1)
        d = result.to_dict()
        assert d["passed"] is False


class TestCellConfig:
    """Test CellConfig model."""

    def test_defaults(self):
        config = CellConfig()
        assert config.band == 1
        assert config.bandwidth_mhz == 10.0
        assert config.dl_level_dbm == -60.0

    def test_to_dict(self):
        config = CellConfig(band=7, bandwidth_mhz=20.0, dl_earfcn=3100)
        d = config.to_dict()
        assert d["band"] == 7
        assert d["bandwidth_mhz"] == 20.0
        assert d["dl_earfcn"] == 3100

    def test_from_dict(self):
        config = CellConfig.from_dict({
            "band": 3,
            "bandwidth_mhz": 5.0,
            "dl_earfcn": 1575,
        })
        assert config.band == 3
        assert config.bandwidth_mhz == 5.0


class TestRFConfig:
    """Test RFConfig model."""

    def test_defaults(self):
        config = RFConfig()
        assert config.frequency_hz == 1e9
        assert config.level_dbm == -60.0

    def test_to_dict(self):
        config = RFConfig(frequency_hz=2.4e9, level_dbm=-40.0)
        d = config.to_dict()
        assert d["frequency_hz"] == 2.4e9

    def test_from_dict(self):
        config = RFConfig.from_dict({"frequency_hz": 5.8e9})
        assert config.frequency_hz == 5.8e9

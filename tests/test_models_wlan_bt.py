"""Tests for WLAN and Bluetooth data models."""

from rs_cmw500_mcp.models.cmw_types import (
    BLEMode,
    BTFrequencyResult,
    BTMeasConfig,
    BTModulationResult,
    BTPacketType,
    BTPowerResult,
    BTTechnology,
    WLANBandwidth,
    WLANEVMResult,
    WLANMeasConfig,
    WLANPowerResult,
    WLANSpectrumFlatnessResult,
    WLANStandard,
)


class TestWLANEnums:
    """Test WLAN enum types."""

    def test_wlan_standard_values(self):
        """WLANStandard should have correct values."""
        assert WLANStandard.AX.value == "AX"
        assert WLANStandard.AC.value == "AC"
        assert WLANStandard.N.value == "N"

    def test_wlan_bandwidth_values(self):
        """WLANBandwidth should have correct values."""
        assert WLANBandwidth.BW20.value == "BW20"
        assert WLANBandwidth.BW80.value == "BW80"
        assert WLANBandwidth.BW160.value == "BW160"


class TestBTEnums:
    """Test Bluetooth enum types."""

    def test_bt_technology_values(self):
        """BTTechnology should have Classic and LE."""
        assert BTTechnology.CLASSIC.value == "CLASsic"
        assert BTTechnology.LE.value == "LENergy"

    def test_ble_mode_values(self):
        """BLEMode should have all PHY modes."""
        assert BLEMode.LE_1M.value == "LE1M"
        assert BLEMode.LE_2M.value == "LE2M"
        assert BLEMode.LE_CODED_S2.value == "LECS2"
        assert BLEMode.LE_CODED_S8.value == "LECS8"

    def test_bt_packet_type_values(self):
        """BTPacketType should include common packet types."""
        assert BTPacketType.DH1.value == "DH1"
        assert BTPacketType.DH5.value == "DH5"
        assert BTPacketType.DM1.value == "DM1"


class TestWLANMeasConfig:
    """Test WLANMeasConfig dataclass."""

    def test_default_values(self):
        """WLANMeasConfig defaults should be sensible."""
        config = WLANMeasConfig()
        assert config.standard == WLANStandard.AX
        assert config.bandwidth == WLANBandwidth.BW80
        assert config.frequency_hz == 5.18e9
        assert config.expected_power_dbm == 20.0
        assert config.meas_instance == 1

    def test_custom_values(self):
        """WLANMeasConfig should accept custom values."""
        config = WLANMeasConfig(
            standard=WLANStandard.AC,
            bandwidth=WLANBandwidth.BW40,
            frequency_hz=5.19e9,
            expected_power_dbm=15.0,
            meas_instance=2,
        )
        assert config.standard == WLANStandard.AC
        assert config.bandwidth == WLANBandwidth.BW40
        assert config.meas_instance == 2


class TestBTMeasConfig:
    """Test BTMeasConfig dataclass."""

    def test_default_values(self):
        """BTMeasConfig defaults should be sensible."""
        config = BTMeasConfig()
        assert config.technology == BTTechnology.LE
        assert config.ble_mode == BLEMode.LE_1M
        assert config.frequency_hz == 2.402e9

    def test_classic_config(self):
        """BTMeasConfig should work for Classic."""
        config = BTMeasConfig(
            technology=BTTechnology.CLASSIC,
            packet_type=BTPacketType.DH5,
        )
        assert config.technology == BTTechnology.CLASSIC
        assert config.packet_type == BTPacketType.DH5


class TestWLANResults:
    """Test WLAN result dataclasses."""

    def test_evm_result_defaults(self):
        """WLANEVMResult should have sensible defaults."""
        result = WLANEVMResult()
        assert result.reliability == ""
        assert result.evm_all_carriers_db is None

    def test_evm_result_with_values(self):
        """WLANEVMResult to_dict should include set values."""
        result = WLANEVMResult(evm_all_carriers_db=-30.0, reliability="0")
        d = result.to_dict()
        assert d["evm_all_carriers_db"] == -30.0

    def test_power_result_defaults(self):
        """WLANPowerResult should have sensible defaults."""
        result = WLANPowerResult()
        assert result.power_dbm is None

    def test_power_result_with_values(self):
        """WLANPowerResult to_dict should include set values."""
        result = WLANPowerResult(power_dbm=20.0)
        d = result.to_dict()
        assert d["power_dbm"] == 20.0

    def test_spectrum_flatness_defaults(self):
        """WLANSpectrumFlatnessResult should have sensible defaults."""
        result = WLANSpectrumFlatnessResult()
        assert result.passed is False


class TestBTResults:
    """Test Bluetooth result dataclasses."""

    def test_modulation_result_defaults(self):
        """BTModulationResult should have sensible defaults."""
        result = BTModulationResult()
        assert result.devm_rms_percent is None

    def test_modulation_result_with_values(self):
        """BTModulationResult to_dict should include set values."""
        result = BTModulationResult(devm_rms_percent=3.5, reliability="0")
        d = result.to_dict()
        assert d["devm_rms_percent"] == 3.5

    def test_power_result_defaults(self):
        """BTPowerResult should have sensible defaults."""
        result = BTPowerResult()
        assert result.power_dbm is None

    def test_frequency_result_defaults(self):
        """BTFrequencyResult should have sensible defaults."""
        result = BTFrequencyResult()
        assert result.initial_offset_khz is None

    def test_bt_power_result_with_values(self):
        """BTPowerResult should store values correctly."""
        result = BTPowerResult(
            reliability="0",
            power_dbm=5.2,
            peak_power_dbm=7.1,
        )
        assert result.power_dbm == 5.2
        assert result.peak_power_dbm == 7.1
        d = result.to_dict()
        assert d["power_dbm"] == 5.2

"""Tests for new templates (BLE TX, BT Classic TX, WLAN RX, BLE RX)."""

import tempfile
from pathlib import Path

from rs_cmw500_mcp.templates.base import MeasurementTemplate
from rs_cmw500_mcp.templates.ble_rx import BLERxTemplate
from rs_cmw500_mcp.templates.ble_tx import BLETxTemplate
from rs_cmw500_mcp.templates.bt_classic_tx import BTClassicTxTemplate
from rs_cmw500_mcp.templates.wlan_rx import WLANRxTemplate


class TestBLETxTemplate:
    """Test BLETxTemplate."""

    def test_defaults(self):
        template = BLETxTemplate()
        assert template.name == "BLE 1M TX"
        assert template.technology == "Bluetooth"
        assert template.parameters["ble_mode"] == "LE1M"

    def test_ble_1m(self):
        template = BLETxTemplate.ble_1m()
        assert template.parameters["ble_mode"] == "LE1M"
        assert template.parameters["frequency_hz"] == 2.402e9

    def test_ble_2m(self):
        template = BLETxTemplate.ble_2m()
        assert template.name == "BLE 2M TX"
        assert template.parameters["ble_mode"] == "LE2M"

    def test_ble_coded_s2(self):
        template = BLETxTemplate.ble_coded_s2()
        assert template.parameters["ble_mode"] == "LECS2"

    def test_to_dict(self):
        template = BLETxTemplate()
        d = template.to_dict()
        assert d["template_type"] == "BLETxTemplate"
        assert d["technology"] == "Bluetooth"

    def test_save_and_load(self):
        template = BLETxTemplate.ble_1m()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            template.save(filepath)
            loaded = MeasurementTemplate.load(filepath)
            assert isinstance(loaded, BLETxTemplate)
            assert loaded.parameters["ble_mode"] == "LE1M"
        finally:
            Path(filepath).unlink(missing_ok=True)


class TestBTClassicTxTemplate:
    """Test BTClassicTxTemplate."""

    def test_defaults(self):
        template = BTClassicTxTemplate()
        assert template.name == "BT Classic DH1 TX"
        assert template.parameters["packet_type"] == "DH1"

    def test_dh1(self):
        template = BTClassicTxTemplate.dh1()
        assert template.parameters["packet_type"] == "DH1"

    def test_dh5(self):
        template = BTClassicTxTemplate.dh5()
        assert template.name == "BT Classic DH5 TX"
        assert template.parameters["packet_type"] == "DH5"

    def test_save_and_load(self):
        template = BTClassicTxTemplate.dh1()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            template.save(filepath)
            loaded = MeasurementTemplate.load(filepath)
            assert isinstance(loaded, BTClassicTxTemplate)
        finally:
            Path(filepath).unlink(missing_ok=True)


class TestWLANRxTemplate:
    """Test WLANRxTemplate."""

    def test_defaults(self):
        template = WLANRxTemplate()
        assert template.name == "WLAN 802.11ax RX Sensitivity"
        assert template.technology == "WLAN"
        assert template.parameters["generator_level_dbm"] == -70.0

    def test_wifi6_80mhz(self):
        template = WLANRxTemplate.wifi6_80mhz()
        assert template.parameters["standard"] == "AX"
        assert template.parameters["bandwidth"] == "BW80"

    def test_wifi6_40mhz(self):
        template = WLANRxTemplate.wifi6_40mhz()
        assert template.parameters["bandwidth"] == "BW40"

    def test_save_and_load(self):
        template = WLANRxTemplate.wifi6_80mhz()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            template.save(filepath)
            loaded = MeasurementTemplate.load(filepath)
            assert isinstance(loaded, WLANRxTemplate)
        finally:
            Path(filepath).unlink(missing_ok=True)


class TestBLERxTemplate:
    """Test BLERxTemplate."""

    def test_defaults(self):
        template = BLERxTemplate()
        assert template.name == "BLE 1M RX Sensitivity"
        assert template.technology == "Bluetooth"

    def test_ble_1m(self):
        template = BLERxTemplate.ble_1m()
        assert template.parameters["ble_mode"] == "LE1M"

    def test_ble_2m(self):
        template = BLERxTemplate.ble_2m()
        assert template.parameters["ble_mode"] == "LE2M"

    def test_save_and_load(self):
        template = BLERxTemplate.ble_1m()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            template.save(filepath)
            loaded = MeasurementTemplate.load(filepath)
            assert isinstance(loaded, BLERxTemplate)
        finally:
            Path(filepath).unlink(missing_ok=True)


class TestTemplateRegistry:
    """Test that new templates are in the template registry."""

    def test_new_templates_in_registry(self):
        from rs_cmw500_mcp.tools.shared import _template_registry

        assert "ble_tx" in _template_registry
        assert "ble_rx" in _template_registry
        assert "bt_classic_tx" in _template_registry
        assert "wlan_rx" in _template_registry

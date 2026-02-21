"""Tests for measurement templates."""

import tempfile
from pathlib import Path

from rs_cmw500_mcp.templates.base import MeasurementTemplate
from rs_cmw500_mcp.templates.gprf_power import GPRFPowerTemplate
from rs_cmw500_mcp.templates.lte_tx import LTETxPowerTemplate
from rs_cmw500_mcp.templates.nonsig_rx import NonSignalingRxTemplate


class TestMeasurementTemplate:
    """Test base MeasurementTemplate."""

    def test_create(self):
        template = MeasurementTemplate(
            name="test",
            description="test template",
            technology="GPRF",
        )
        assert template.name == "test"
        assert template.technology == "GPRF"

    def test_to_dict(self):
        template = MeasurementTemplate(
            name="test",
            description="desc",
            technology="LTE",
            parameters={"band": 1},
        )
        d = template.to_dict()
        assert d["name"] == "test"
        assert d["technology"] == "LTE"
        assert d["parameters"]["band"] == 1
        assert d["template_type"] == "MeasurementTemplate"

    def test_from_dict(self):
        data = {
            "name": "test",
            "description": "desc",
            "technology": "GPRF",
            "parameters": {"freq": 1e9},
        }
        template = MeasurementTemplate.from_dict(data)
        assert template.name == "test"
        assert template.parameters["freq"] == 1e9

    def test_get_summary(self):
        template = MeasurementTemplate(
            name="test",
            description="desc",
            technology="GPRF",
        )
        summary = template.get_summary()
        assert summary["name"] == "test"
        assert "template_type" in summary

    def test_save_and_load(self):
        template = MeasurementTemplate(
            name="save_test",
            description="save test template",
            technology="GPRF",
            parameters={"freq": 1e9},
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            template.save(filepath)
            loaded = MeasurementTemplate.load(filepath)
            assert loaded.name == "save_test"
            assert loaded.parameters["freq"] == 1e9
        finally:
            Path(filepath).unlink(missing_ok=True)


class TestLTETxPowerTemplate:
    """Test LTETxPowerTemplate."""

    def test_defaults(self):
        template = LTETxPowerTemplate()
        assert template.name == "LTE TX Power"
        assert template.technology == "LTE"
        assert "band" in template.parameters
        assert "bandwidth_mhz" in template.parameters

    def test_create(self):
        template = LTETxPowerTemplate.create(
            band=7,
            bandwidth_mhz=20.0,
            dl_earfcn=3100,
        )
        assert template.parameters["band"] == 7
        assert template.parameters["bandwidth_mhz"] == 20.0

    def test_to_dict(self):
        template = LTETxPowerTemplate()
        d = template.to_dict()
        assert d["template_type"] == "LTETxPowerTemplate"

    def test_save_and_load(self):
        template = LTETxPowerTemplate.create(band=3, bandwidth_mhz=10.0)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            template.save(filepath)
            loaded = MeasurementTemplate.load(filepath)
            assert isinstance(loaded, LTETxPowerTemplate)
            assert loaded.parameters["band"] == 3
        finally:
            Path(filepath).unlink(missing_ok=True)


class TestGPRFPowerTemplate:
    """Test GPRFPowerTemplate."""

    def test_defaults(self):
        template = GPRFPowerTemplate()
        assert template.name == "GPRF Power Measurement"
        assert template.technology == "GPRF"
        assert "frequency_hz" in template.parameters

    def test_create(self):
        template = GPRFPowerTemplate.create(
            frequency_hz=2.4e9,
            expected_power_dbm=10.0,
        )
        assert template.parameters["frequency_hz"] == 2.4e9
        assert template.parameters["expected_power_dbm"] == 10.0

    def test_save_and_load(self):
        template = GPRFPowerTemplate.create(frequency_hz=5.8e9)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            template.save(filepath)
            loaded = MeasurementTemplate.load(filepath)
            assert isinstance(loaded, GPRFPowerTemplate)
        finally:
            Path(filepath).unlink(missing_ok=True)


class TestNonSignalingRxTemplate:
    """Test NonSignalingRxTemplate."""

    def test_defaults(self):
        template = NonSignalingRxTemplate()
        assert template.name == "Non-Signaling RX Test"
        assert "generator_level_dbm" in template.parameters

    def test_create(self):
        template = NonSignalingRxTemplate.create(
            frequency_hz=1.8e9,
            generator_level_dbm=-90.0,
        )
        assert template.parameters["frequency_hz"] == 1.8e9
        assert template.parameters["generator_level_dbm"] == -90.0

    def test_save_and_load(self):
        template = NonSignalingRxTemplate.create()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            template.save(filepath)
            loaded = MeasurementTemplate.load(filepath)
            assert isinstance(loaded, NonSignalingRxTemplate)
        finally:
            Path(filepath).unlink(missing_ok=True)

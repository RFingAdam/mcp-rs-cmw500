"""Tests for security hardening: SCPI sanitization, path validation, raw SCPI guards."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from rs_cmw500_mcp.config import CMWSettings
from rs_cmw500_mcp.safety.validators import sanitize_scpi_param, validate_safe_path

# =============================================================================
# Issue 1: sanitize_scpi_param tests
# =============================================================================


class TestSanitizeScpiParam:
    """Tests for SCPI parameter sanitization."""

    def test_clean_string_passes(self):
        """Normal strings should pass through unchanged."""
        assert sanitize_scpi_param("hello") == "hello"
        assert sanitize_scpi_param("test_file") == "test_file"
        assert sanitize_scpi_param("001") == "001"
        assert sanitize_scpi_param("band7_10mhz") == "band7_10mhz"

    def test_empty_string_passes(self):
        """Empty string should pass through."""
        assert sanitize_scpi_param("") == ""

    def test_numeric_string_passes(self):
        """Numeric strings should pass through."""
        assert sanitize_scpi_param("12345") == "12345"
        assert sanitize_scpi_param("-30.5") == "-30.5"

    def test_file_path_on_instrument_passes(self):
        """CMW500 instrument file paths (no semicolons/newlines) should pass."""
        assert sanitize_scpi_param("C:\\R_S\\CMW\\waveform.wv") == "C:\\R_S\\CMW\\waveform.wv"
        path = "/usr/local/waveforms/test.arb"
        assert sanitize_scpi_param(path) == path

    def test_semicolon_rejected(self):
        """Semicolons (SCPI command separator) must be rejected."""
        with pytest.raises(ValueError, match="prohibited characters"):
            sanitize_scpi_param("test;*RST")

    def test_semicolon_at_end_rejected(self):
        """Trailing semicolons must also be rejected."""
        with pytest.raises(ValueError, match="prohibited characters"):
            sanitize_scpi_param("SOME:COMMAND;")

    def test_rst_injection_rejected(self):
        """Classic ;*RST injection must be rejected."""
        with pytest.raises(ValueError, match="prohibited characters"):
            sanitize_scpi_param("value;*RST")

    def test_cls_injection_rejected(self):
        """Classic ;*CLS injection must be rejected."""
        with pytest.raises(ValueError, match="prohibited characters"):
            sanitize_scpi_param("value;*CLS")

    def test_newline_injection_rejected(self):
        """Newline characters must be rejected (could inject commands on new lines)."""
        with pytest.raises(ValueError, match="prohibited characters"):
            sanitize_scpi_param("value\nSOURce:GPRF:GENerator1:STATe ON")

    def test_carriage_return_rejected(self):
        """Carriage return must be rejected."""
        with pytest.raises(ValueError, match="prohibited characters"):
            sanitize_scpi_param("value\rSOURce:GPRF:GENerator1:STATe ON")

    def test_crlf_injection_rejected(self):
        """CR+LF injection must be rejected."""
        with pytest.raises(ValueError, match="prohibited characters"):
            sanitize_scpi_param("value\r\n*RST")

    def test_star_at_start_rejected(self):
        """Leading * must be rejected (could trigger instrument commands)."""
        with pytest.raises(ValueError, match="must not start with"):
            sanitize_scpi_param("*RST")

    def test_star_with_leading_space_rejected(self):
        """Leading space then * must be rejected."""
        with pytest.raises(ValueError, match="must not start with"):
            sanitize_scpi_param("  *OPC")

    def test_star_in_middle_passes(self):
        """Star in the middle of a string (not leading) should pass."""
        assert sanitize_scpi_param("file*name") == "file*name"

    def test_non_string_rejected(self):
        """Non-string types must be rejected."""
        with pytest.raises(ValueError, match="Expected string"):
            sanitize_scpi_param(123)  # type: ignore

        with pytest.raises(ValueError, match="Expected string"):
            sanitize_scpi_param(None)  # type: ignore

    def test_multiple_injection_vectors(self):
        """Multiple injection vectors in one string."""
        with pytest.raises(ValueError):
            sanitize_scpi_param("test;*RST\n*CLS")

    def test_mcc_mnc_valid(self):
        """Typical MCC/MNC values should pass."""
        assert sanitize_scpi_param("001") == "001"
        assert sanitize_scpi_param("01") == "01"
        assert sanitize_scpi_param("310") == "310"
        assert sanitize_scpi_param("260") == "260"

    def test_mcc_injection(self):
        """MCC field with injection payload must be rejected."""
        with pytest.raises(ValueError):
            sanitize_scpi_param("001;*RST")


# =============================================================================
# Issue 2: validate_safe_path tests
# =============================================================================


class TestValidateSafePath:
    """Tests for file path validation against traversal and symlink attacks."""

    def setup_method(self):
        """Create temporary base directory for tests."""
        self.tmpdir = tempfile.mkdtemp()
        self.base_dir = Path(self.tmpdir) / "cmw_states"
        self.base_dir.mkdir()

    def teardown_method(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_simple_filename_passes(self):
        """Simple filename resolves within base dir."""
        result = validate_safe_path("test.json", self.base_dir)
        assert result == self.base_dir.resolve() / "test.json"

    def test_nested_path_passes(self):
        """Nested subdirectory path should pass if within base."""
        result = validate_safe_path("subdir/test.json", self.base_dir)
        assert result.is_relative_to(self.base_dir.resolve())

    def test_dot_slash_traversal_rejected(self):
        """../ directory traversal must be rejected."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_safe_path("../../etc/passwd", self.base_dir)

    def test_deep_traversal_rejected(self):
        """Deep ../ traversal must be rejected."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_safe_path("../../../../../../../etc/shadow", self.base_dir)

    def test_absolute_path_outside_rejected(self):
        """Absolute path outside base dir must be rejected."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_safe_path("/etc/passwd", self.base_dir)

    def test_absolute_path_inside_passes(self):
        """Absolute path that happens to be inside base dir should pass."""
        inside_path = self.base_dir.resolve() / "test.json"
        # We construct a relative path from base to target
        result = validate_safe_path("test.json", self.base_dir)
        assert result == inside_path

    def test_dot_dot_in_middle_rejected(self):
        """Path with .. component that escapes base must be rejected."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_safe_path("subdir/../../outside.json", self.base_dir)

    def test_symlink_outside_base_rejected(self):
        """Symlink pointing outside base dir must be rejected."""
        # Create a symlink inside base_dir that points to /tmp
        link_path = self.base_dir / "evil_link"
        target_outside = Path(self.tmpdir) / "outside_file.json"
        target_outside.touch()

        try:
            link_path.symlink_to(target_outside)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        with pytest.raises(ValueError, match="(Path traversal|Symlink escape)"):
            validate_safe_path("evil_link", self.base_dir)

    def test_path_with_null_bytes(self):
        """Path with null bytes should raise (OS-level protection)."""
        with pytest.raises((ValueError, OSError)):
            validate_safe_path("test\x00.json", self.base_dir)

    def test_encoded_traversal_rejected(self):
        """Various traversal encodings must be rejected."""
        # Forward-slash traversal is always resolved by Path.resolve()
        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_safe_path("subdir/../../../etc/passwd", self.base_dir)

    def test_path_with_spaces_passes(self):
        """Filenames with spaces should pass."""
        result = validate_safe_path("my state file.json", self.base_dir)
        assert result.is_relative_to(self.base_dir.resolve())

    def test_returns_resolved_path(self):
        """Result should be a fully resolved Path."""
        result = validate_safe_path("test.json", self.base_dir)
        # resolve() should be idempotent on the result
        assert result == result.resolve()


# =============================================================================
# Issue 3: Raw SCPI guard tests
# =============================================================================


class TestRawScpiGuard:
    """Tests for raw SCPI safety guard and logging."""

    def test_config_allow_raw_scpi_default_true(self):
        """Default config should allow raw SCPI (backwards compat)."""
        settings = CMWSettings()
        assert settings.allow_raw_scpi is True

    def test_config_allow_raw_scpi_can_be_disabled(self):
        """allow_raw_scpi can be set to False."""
        settings = CMWSettings(allow_raw_scpi=False)
        assert settings.allow_raw_scpi is False

    def test_config_from_env_variable(self):
        """allow_raw_scpi should be configurable via CMW_ALLOW_RAW_SCPI env var."""
        with patch.dict(os.environ, {"CMW_ALLOW_RAW_SCPI": "false"}):
            settings = CMWSettings()
            assert settings.allow_raw_scpi is False

    @pytest.mark.asyncio
    async def test_scpi_send_blocked_when_disabled(self):
        """cmw_scpi_send should return error when raw SCPI is disabled."""
        from rs_cmw500_mcp.tools import handle_tool

        with patch("rs_cmw500_mcp.tools.scpi.get_settings") as mock_settings:
            settings = CMWSettings(allow_raw_scpi=False)
            mock_settings.return_value = settings

            result = await handle_tool("cmw_scpi_send", {"command": "*RST"})
            assert len(result.content) == 1
            assert result.isError is True
            text = result.content[0].text.lower()
            assert "disabled" in text or "error" in text

    @pytest.mark.asyncio
    async def test_scpi_query_blocked_when_disabled(self):
        """cmw_scpi_query should return error when raw SCPI is disabled."""
        from rs_cmw500_mcp.tools import handle_tool

        with patch("rs_cmw500_mcp.tools.scpi.get_settings") as mock_settings:
            settings = CMWSettings(allow_raw_scpi=False)
            mock_settings.return_value = settings

            result = await handle_tool("cmw_scpi_query", {"command": "*IDN?"})
            assert len(result.content) == 1
            assert result.isError is True
            text = result.content[0].text.lower()
            assert "disabled" in text or "error" in text

    @pytest.mark.asyncio
    async def test_scpi_send_logs_warning_when_enabled(self):
        """cmw_scpi_send should log WARNING with command when allowed."""
        from rs_cmw500_mcp.tools import handle_tool
        from rs_cmw500_mcp.tools import scpi as scpi_module

        mock_cmw = AsyncMock()
        mock_cmw.is_connected = True

        with (
            patch("rs_cmw500_mcp.tools.scpi.get_settings") as mock_settings,
            patch("rs_cmw500_mcp.tools.scpi._get_cmw", return_value=mock_cmw),
            patch.object(scpi_module.logger, "warning") as mock_warning,
        ):
            settings = CMWSettings(allow_raw_scpi=True)
            mock_settings.return_value = settings

            await handle_tool("cmw_scpi_send", {"command": "SYSTem:PRESet"})

            mock_warning.assert_called_once()
            call_args = mock_warning.call_args[0][0]
            assert "SYSTem:PRESet" in call_args
            assert "Raw SCPI" in call_args

    @pytest.mark.asyncio
    async def test_scpi_query_logs_warning_when_enabled(self):
        """cmw_scpi_query should log WARNING with command when allowed."""
        from rs_cmw500_mcp.tools import handle_tool
        from rs_cmw500_mcp.tools import scpi as scpi_module

        mock_cmw = AsyncMock()
        mock_cmw.is_connected = True
        mock_cmw.scpi_query = AsyncMock(return_value="some_response")

        with (
            patch("rs_cmw500_mcp.tools.scpi.get_settings") as mock_settings,
            patch("rs_cmw500_mcp.tools.scpi._get_cmw", return_value=mock_cmw),
            patch.object(scpi_module.logger, "warning") as mock_warning,
        ):
            settings = CMWSettings(allow_raw_scpi=True)
            mock_settings.return_value = settings

            await handle_tool("cmw_scpi_query", {"command": "*IDN?"})

            mock_warning.assert_called_once()
            call_args = mock_warning.call_args[0][0]
            assert "*IDN?" in call_args
            assert "Raw SCPI" in call_args

    @pytest.mark.asyncio
    async def test_scpi_send_error_message_includes_setting_name(self):
        """Error message should tell user how to enable raw SCPI."""
        from rs_cmw500_mcp.tools import handle_tool

        with patch("rs_cmw500_mcp.tools.scpi.get_settings") as mock_settings:
            settings = CMWSettings(allow_raw_scpi=False)
            mock_settings.return_value = settings

            result = await handle_tool("cmw_scpi_send", {"command": "*RST"})
            assert result.isError is True
            assert "CMW_ALLOW_RAW_SCPI" in result.content[0].text


# =============================================================================
# Integration: Sanitizer applied in driver methods
# =============================================================================


class TestDriverSanitization:
    """Tests that driver methods properly sanitize string parameters."""

    @pytest.mark.asyncio
    async def test_gen_load_arb_rejects_injection(self):
        """gen_load_arb should reject file paths with SCPI injection."""
        from rs_cmw500_mcp.driver.cmw500_driver import CMW500Driver

        driver = CMW500Driver.__new__(CMW500Driver)
        driver._scpi = AsyncMock()
        driver._safety = AsyncMock()

        with pytest.raises(ValueError, match="prohibited characters"):
            await driver.gen_load_arb("waveform.wv;*RST")

    @pytest.mark.asyncio
    async def test_gen_load_arb_rejects_newline(self):
        """gen_load_arb should reject file paths with newlines."""
        from rs_cmw500_mcp.driver.cmw500_driver import CMW500Driver

        driver = CMW500Driver.__new__(CMW500Driver)
        driver._scpi = AsyncMock()
        driver._safety = AsyncMock()

        with pytest.raises(ValueError, match="prohibited characters"):
            await driver.gen_load_arb("waveform.wv\n*RST")

    @pytest.mark.asyncio
    async def test_lte_configure_nas_rejects_injection(self):
        """lte_configure_nas should reject MCC/MNC with injection payload."""
        from rs_cmw500_mcp.driver.cmw500_driver import CMW500Driver

        driver = CMW500Driver.__new__(CMW500Driver)
        driver._scpi = AsyncMock()
        driver._safety = AsyncMock()

        with pytest.raises(ValueError, match="prohibited characters"):
            await driver.lte_configure_nas("001;*RST", "01")

    @pytest.mark.asyncio
    async def test_lte_configure_nas_clean_values_pass(self):
        """lte_configure_nas should accept clean MCC/MNC values."""
        from rs_cmw500_mcp.driver.cmw500_driver import CMW500Driver

        driver = CMW500Driver.__new__(CMW500Driver)
        driver._scpi = AsyncMock()
        driver._safety = AsyncMock()

        await driver.lte_configure_nas("001", "01")
        assert driver._scpi.send.call_count == 2

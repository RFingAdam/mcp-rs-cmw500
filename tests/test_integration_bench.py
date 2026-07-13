"""Hardware integration bench checks.

These run ONLY when CMW_TEST_HOST points at a real CMW500 (see the
skip_without_cmw fixture in conftest.py). They are the operator's post-build
validation: identify the unit, list options, self-test licensed domains, and run
a tiny read-only test plan. Deselect in CI with `-m "not integration"`.
"""

import json
import os

import pytest

from rs_cmw500_mcp.tools import handle_tool


@pytest.mark.integration
class TestBench:
    @pytest.mark.asyncio
    async def test_identify(self, skip_without_cmw, cmw_test_config):
        res = await handle_tool("cmw_identify", cmw_test_config)
        assert res.isError is False

    @pytest.mark.asyncio
    async def test_selftest_reports_domains(self, skip_without_cmw, cmw_test_config):
        res = await handle_tool("cmw_selftest", {**cmw_test_config, "run_smoke": True})
        assert res.isError is False
        data = json.loads(res.content[0].text)
        assert "options" in data and "domains" in data

    @pytest.mark.asyncio
    async def test_readonly_testplan(self, skip_without_cmw, cmw_test_config):
        define = await handle_tool(
            "cmw_testplan_define",
            {
                "name": "bench-smoke",
                "host": cmw_test_config["host"],
                "port": cmw_test_config["port"],
                "steps": [
                    {"name": "idn", "tool": "cmw_identify"},
                    {"name": "opts", "tool": "cmw_query_options"},
                    {"name": "status", "tool": "cmw_get_status"},
                ],
            },
        )
        run_id = json.loads(define.content[0].text)["run_id"]
        await handle_tool("cmw_testplan_run", {"run_id": run_id})
        report = await handle_tool("cmw_testplan_report", {"run_id": run_id, "format": "markdown"})
        assert "bench-smoke" in json.loads(report.content[0].text)["content"]


# If the profile-based test host is set, load it before the bench checks.
if os.environ.get("CMW_TEST_PROFILE"):  # pragma: no cover - hardware only
    from rs_cmw500_mcp.profile import load_active_profile

    load_active_profile(os.environ["CMW_TEST_PROFILE"])

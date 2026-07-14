"""Tests for test-plan report renderers (Markdown / HTML / CSV)."""

import csv
import io

from rs_cmw500_mcp.testplan import render_csv, render_html, render_markdown
from rs_cmw500_mcp.testplan.models import StepResult, TestRunResult


def _sample_run() -> TestRunResult:
    return TestRunResult(
        run_id="abc123",
        plan_name="Smoke",
        status="complete",
        started_at="2026-07-13T00:00:00+00:00",
        finished_at="2026-07-13T00:01:00+00:00",
        total_steps=2,
        passed=1,
        failed=1,
        environment={"profile": "bench-1"},
        steps=[
            StepResult(
                index=0,
                name="power",
                tool="cmw_meas_fetch_power",
                role="main",
                status="pass",
                measurements={"power.current_dbm": -20.0},
                limit_result={"passed": True, "total_checks": 1, "failed_checks": 0},
            ),
            StepResult(
                index=1,
                name="evm",
                tool="cmw_lte_meas_fetch_evm",
                role="main",
                status="fail",
                measurements={"evm_rms_percent": 5.0},
                limit_result={"passed": False, "total_checks": 1, "failed_checks": 1},
            ),
        ],
    )


class TestReports:
    def test_markdown(self):
        md = render_markdown(_sample_run())
        assert "# Test report: Smoke" in md
        assert "**Overall: FAIL**" in md  # one step failed
        assert "PASS" in md and "FAIL" in md
        assert "cmw_meas_fetch_power" in md

    def test_html_self_contained(self):
        html_doc = render_html(_sample_run())
        assert "<style>" in html_doc  # inline CSS
        assert "http://" not in html_doc and "https://" not in html_doc  # no external refs
        assert "Smoke" in html_doc

    def test_csv_rows(self):
        text = render_csv(_sample_run())
        rows = list(csv.reader(io.StringIO(text)))
        assert rows[0] == [
            "run_id",
            "step_index",
            "step",
            "tool",
            "role",
            "verdict",
            "parameter",
            "measured",
        ]
        # one data row per checked parameter
        data = rows[1:]
        assert len(data) == 2
        assert data[0][6] == "power.current_dbm"
        assert data[1][5] == "FAIL"

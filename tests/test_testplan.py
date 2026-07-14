"""Tests for the test-plan engine (models + resumable runner)."""

import json
from typing import Any

import pytest
from mcp.types import Tool

from rs_cmw500_mcp.testplan import TestPlan, TestRun
from rs_cmw500_mcp.testplan.models import flatten_numeric, get_dotted
from rs_cmw500_mcp.tools import handle_tool
from rs_cmw500_mcp.tools.registry import registry
from rs_cmw500_mcp.tools.shared import _format_error, _format_result


@pytest.fixture
def fake_tools():
    """Register throwaway tools for the run; clean them up afterward."""

    async def tp_measure(args: dict[str, Any]):
        return _format_result(
            {"power": {"current_dbm": -20.0}, "evm": 2.5, "ok": True, "label": "fine"}
        )

    async def tp_echo(args: dict[str, Any]):
        return _format_result({"received": args})

    async def tp_sweepish(args: dict[str, Any]):
        return _format_result({"sweep_id": "abc123"})

    async def tp_boom(args: dict[str, Any]):
        return _format_error(ValueError("kaboom"))

    async def tp_teardown(args: dict[str, Any]):
        return _format_result({"status": "ok", "off": True})

    names = {
        "tp_measure": tp_measure,
        "tp_echo": tp_echo,
        "tp_sweepish": tp_sweepish,
        "tp_boom": tp_boom,
        "tp_teardown": tp_teardown,
    }
    for name, handler in names.items():
        registry.register(
            Tool(name=name, description="test", inputSchema={"type": "object"}), handler
        )
    yield
    for name in names:
        registry._tools.pop(name, None)
        registry._handlers.pop(name, None)


class TestFlatten:
    def test_nested_and_types(self):
        flat = flatten_numeric(
            {"power": {"current_dbm": -20.0}, "evm": "2.5", "ok": True, "label": "x", "arr": [1, 2]}
        )
        assert flat["power.current_dbm"] == -20.0
        assert flat["evm"] == 2.5  # str coerced
        assert "ok" not in flat  # bool skipped
        assert "label" not in flat  # non-numeric str
        assert flat["arr.0"] == 1.0 and flat["arr.1"] == 2.0

    def test_get_dotted(self):
        obj = {"a": {"b": [{"c": 7}]}}
        assert get_dotted(obj, "a.b.0.c") == 7
        assert get_dotted(obj, "a.x") is None


class TestRunner:
    @pytest.mark.asyncio
    async def test_pass_and_fail_limits(self, fake_tools):
        plan = TestPlan.from_dict(
            {
                "name": "p",
                "steps": [
                    {
                        "name": "hi-limit",
                        "tool": "tp_measure",
                        "limits": [{"parameter": "power.current_dbm", "max_value": -10}],
                    },
                    {
                        "name": "lo-limit",
                        "tool": "tp_measure",
                        "limits": [{"parameter": "power.current_dbm", "min_value": -10}],
                    },
                ],
            }
        )
        run = TestRun("r1", plan)
        await run.run()
        res = run.result()
        assert res["steps"][0]["status"] == "pass"  # -20 <= -10
        assert res["steps"][1]["status"] == "fail"  # -20 < -10 min
        assert res["summary"]["passed"] == 1 and res["summary"]["failed"] == 1

    @pytest.mark.asyncio
    async def test_unmatched_parameter_fails(self, fake_tools):
        plan = TestPlan.from_dict(
            {
                "name": "p",
                "steps": [
                    {
                        "name": "bad-path",
                        "tool": "tp_measure",
                        "limits": [{"parameter": "nope.missing", "max_value": 1}],
                    }
                ],
            }
        )
        run = TestRun("r2", plan)
        await run.run()
        step = run.result()["steps"][0]
        assert step["status"] == "fail"
        assert "not found" in step["note"]

    @pytest.mark.asyncio
    async def test_resumable_progress(self, fake_tools):
        plan = TestPlan.from_dict(
            {
                "name": "p",
                "steps": [{"name": "a", "tool": "tp_measure"}, {"name": "b", "tool": "tp_measure"}],
            }
        )
        run = TestRun("r3", plan)
        prog = await run.step(1)
        assert prog["progress"] == {"done": 1, "total": 2, "percent": 50.0}
        assert prog["status"] == "running"
        await run.step(1)
        assert run.done and run.result()["status"] == "complete"

    @pytest.mark.asyncio
    async def test_abort_skips_main_but_runs_teardown(self, fake_tools):
        plan = TestPlan.from_dict(
            {
                "name": "p",
                "steps": [
                    {
                        "name": "fail-hard",
                        "tool": "tp_measure",
                        "abort_on_fail": True,
                        "limits": [{"parameter": "power.current_dbm", "min_value": 0}],
                    },
                    {"name": "should-skip", "tool": "tp_measure"},
                    {"name": "cleanup", "tool": "tp_teardown", "role": "teardown"},
                ],
            }
        )
        run = TestRun("r4", plan)
        await run.run()
        steps = {s["name"]: s["status"] for s in run.result()["steps"]}
        assert steps["fail-hard"] == "fail"
        assert steps["should-skip"] == "skipped"
        assert steps["cleanup"] == "pass"  # teardown still executed
        assert run.result()["status"] == "aborted"

    @pytest.mark.asyncio
    async def test_context_chaining(self, fake_tools):
        plan = TestPlan.from_dict(
            {
                "name": "p",
                "steps": [
                    {"name": "make", "tool": "tp_sweepish", "save_as": {"sweep_id": "sid"}},
                    {"name": "use", "tool": "tp_echo", "args": {"x": "${ctx.sid}"}},
                ],
            }
        )
        run = TestRun("r5", plan)
        await run.run()
        echoed = run.result()["steps"][1]["result"]["received"]
        assert echoed["x"] == "abc123"

    @pytest.mark.asyncio
    async def test_error_step(self, fake_tools):
        plan = TestPlan.from_dict({"name": "p", "steps": [{"name": "boom", "tool": "tp_boom"}]})
        run = TestRun("r6", plan)
        await run.run()
        step = run.result()["steps"][0]
        assert step["status"] == "error" and step["is_error"] is True


class TestEndToEndViaDispatch:
    """Full define -> run -> report through the real MCP dispatch path, using the
    hardware-free IMD planner tool as a step (no instrument needed)."""

    @pytest.mark.asyncio
    async def test_imd_plan_passes_and_reports(self):
        define = await handle_tool(
            "cmw_testplan_define",
            {
                "name": "imd-check",
                "steps": [
                    {
                        "name": "b8-harmonic-into-1800",
                        "tool": "cmw_imd_analyze",
                        "args": {"carrier1": "LTE_B8", "victim": "1800-1810"},
                        "limits": [{"parameter": "hit_count", "min_value": 1}],
                    }
                ],
            },
        )
        run_id = json.loads(define.content[0].text)["run_id"]

        await handle_tool("cmw_testplan_run", {"run_id": run_id})
        result = json.loads(
            (await handle_tool("cmw_testplan_result", {"run_id": run_id})).content[0].text
        )
        assert result["status"] == "complete"
        assert result["summary"]["passed"] == 1

        report = json.loads(
            (await handle_tool("cmw_testplan_report", {"run_id": run_id, "format": "markdown"}))
            .content[0]
            .text
        )
        assert report["overall_passed"] is True
        assert "imd-check" in report["content"]

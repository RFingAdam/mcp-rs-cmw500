"""Test-plan + reporting MCP tools.

Define a plan (steps that invoke any registered tool), run it step-by-step or
unattended, read results, and render a Markdown/HTML/CSV report. Plans are
saveable/loadable JSON for a reusable test library.
"""

import logging
import uuid
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult, Tool

from ..config import get_settings
from ..profile import get_active_profile
from ..safety.validators import validate_safe_path
from ..testplan import TestPlan, TestRun, render_csv, render_html, render_markdown
from .registry import registry
from .shared import _format_error, _format_result

logger = logging.getLogger(__name__)

# Server-side run store, keyed by run_id (like tools/coex.py::_sweeps).
_runs: dict[str, TestRun] = {}

_RUN_ID = {"run_id": {"type": "string"}}


def _get_run(run_id: str) -> TestRun | None:
    return _runs.get(run_id)


async def _handle_testplan_define(args: dict[str, Any]) -> CallToolResult:
    try:
        plan = TestPlan.from_dict(
            {
                "name": args["name"],
                "description": args.get("description", ""),
                "host": args.get("host"),
                "port": args.get("port"),
                "steps": args.get("steps", []),
            }
        )
    except (KeyError, ValueError) as exc:
        return _format_error(ValueError(f"Invalid test plan: {exc}"))
    if not plan.steps:
        return _format_error(ValueError("Test plan has no steps."))

    run_id = uuid.uuid4().hex[:12]
    run = TestRun(run_id, plan)
    profile = get_active_profile()
    run.environment = {
        "profile": profile.name if profile else None,
        "host": run.host or get_settings().default_host,
        "port": run.port or get_settings().default_port,
    }
    _runs[run_id] = run
    preview = [{"name": s.name, "tool": s.tool, "role": s.role} for s in plan.steps[:8]]
    return _format_result(
        {
            "run_id": run_id,
            "plan_name": plan.name,
            "total_steps": run.total,
            "steps_preview": preview,
        }
    )


async def _handle_testplan_step(args: dict[str, Any]) -> CallToolResult:
    run = _get_run(args.get("run_id", ""))
    if run is None:
        return _format_error(ValueError(f"Unknown run_id: {args.get('run_id')!r}"))
    return _format_result(await run.step(max_steps=int(args.get("max_steps", 1))))


async def _handle_testplan_run(args: dict[str, Any]) -> CallToolResult:
    run = _get_run(args.get("run_id", ""))
    if run is None:
        return _format_error(ValueError(f"Unknown run_id: {args.get('run_id')!r}"))
    return _format_result(await run.run())


async def _handle_testplan_result(args: dict[str, Any]) -> CallToolResult:
    run = _get_run(args.get("run_id", ""))
    if run is None:
        return _format_error(ValueError(f"Unknown run_id: {args.get('run_id')!r}"))
    return _format_result(run.result(include_results=bool(args.get("include_results", True))))


async def _handle_testplan_report(args: dict[str, Any]) -> CallToolResult:
    run = _get_run(args.get("run_id", ""))
    if run is None:
        return _format_error(ValueError(f"Unknown run_id: {args.get('run_id')!r}"))
    fmt = args.get("format", "markdown").lower()
    rr = run.to_run_result()
    renderers = {"markdown": render_markdown, "html": render_html, "csv": render_csv}
    if fmt not in renderers:
        return _format_error(ValueError(f"format must be one of {list(renderers)}"))
    content = renderers[fmt](rr)

    written: str | None = None
    if args.get("filename"):
        ext = {"markdown": "md", "html": "html", "csv": "csv"}[fmt]
        safe = Path(args["filename"]).name
        path = validate_safe_path(f"{safe}.{ext}", get_settings().report_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written = str(path)

    return _format_result(
        {
            "format": fmt,
            "written_to": written,
            "overall_passed": rr.overall_passed,
            "content": content,
        }
    )


async def _handle_testplan_save(args: dict[str, Any]) -> CallToolResult:
    run = _get_run(args["run_id"]) if args.get("run_id") else None
    if args.get("plan"):
        plan = TestPlan.from_dict(args["plan"])
    elif run is not None:
        plan = run.plan
    else:
        return _format_error(ValueError("Provide 'plan' or a valid 'run_id' to save."))
    safe = Path(args["filename"]).name
    path = validate_safe_path(f"{safe}.json", get_settings().testplan_dir)
    plan.save(path)
    return _format_result({"status": "ok", "saved_to": str(path), "plan_name": plan.name})


async def _handle_testplan_load(args: dict[str, Any]) -> CallToolResult:
    safe = Path(args["filename"]).name
    path = validate_safe_path(f"{safe}.json", get_settings().testplan_dir)
    if not path.exists():
        return _format_error(FileNotFoundError(f"Test plan not found: {path}"))
    plan = TestPlan.load(path)
    run_id = uuid.uuid4().hex[:12]
    _runs[run_id] = TestRun(run_id, plan)
    return _format_result(
        {"run_id": run_id, "plan_name": plan.name, "total_steps": len(plan.steps)}
    )


async def _handle_testplan_list(args: dict[str, Any]) -> CallToolResult:
    base = Path(get_settings().testplan_dir)
    plans: list[dict[str, Any]] = []
    if base.exists():
        for filepath in sorted(base.glob("*.json")):
            try:
                p = TestPlan.load(filepath)
                plans.append(
                    {
                        "name": p.name,
                        "description": p.description,
                        "steps": len(p.steps),
                        "file": filepath.stem,
                    }
                )
            except (OSError, ValueError) as exc:
                logger.debug("Skipping unreadable plan %s: %s", filepath, exc)
    return _format_result({"plans": plans, "count": len(plans)})


# =============================================================================
# Registration
# =============================================================================

_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "tool": {"type": "string", "description": "Any registered tool name"},
        "args": {"type": "object"},
        "role": {"type": "string", "enum": ["setup", "main", "teardown"], "default": "main"},
        "abort_on_fail": {"type": "boolean", "default": False},
        "continue_on_error": {"type": "boolean", "default": True},
        "save_as": {
            "type": "object",
            "description": "result-dotted-path -> context key (use later via ${ctx.key})",
            "additionalProperties": {"type": "string"},
        },
        "limits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "parameter": {"type": "string", "description": "dotted result path"},
                    "max_value": {"type": "number"},
                    "min_value": {"type": "number"},
                    "unit": {"type": "string"},
                },
                "required": ["parameter"],
            },
        },
    },
    "required": ["name", "tool"],
}

registry.register(
    Tool(
        name="cmw_testplan_define",
        description=(
            "Define a test plan: ordered steps that each invoke any registered tool, "
            "optionally with pass/fail limits on dotted result paths and ${ctx.key} "
            "chaining. Returns a run_id; then call cmw_testplan_step/run."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "steps": {"type": "array", "items": _STEP_SCHEMA},
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
            "required": ["name", "steps"],
        },
    ),
    _handle_testplan_define,
)

registry.register(
    Tool(
        name="cmw_testplan_step",
        description="Run the next N steps of a test-plan run (default 1); returns progress.",
        inputSchema={
            "type": "object",
            "properties": {**_RUN_ID, "max_steps": {"type": "integer", "default": 1}},
            "required": ["run_id"],
        },
    ),
    _handle_testplan_step,
)

registry.register(
    Tool(
        name="cmw_testplan_run",
        description="Run a test-plan run to completion (unattended).",
        inputSchema={"type": "object", "properties": {**_RUN_ID}, "required": ["run_id"]},
    ),
    _handle_testplan_run,
)

registry.register(
    Tool(
        name="cmw_testplan_result",
        description="Return a test-plan run's full results (steps + verdicts).",
        inputSchema={
            "type": "object",
            "properties": {**_RUN_ID, "include_results": {"type": "boolean", "default": True}},
            "required": ["run_id"],
        },
    ),
    _handle_testplan_result,
)

registry.register(
    Tool(
        name="cmw_testplan_report",
        description=(
            "Render a run to a report: format 'markdown' | 'html' | 'csv'. Returns the "
            "content inline; if 'filename' is given, also writes it under the report dir."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                **_RUN_ID,
                "format": {
                    "type": "string",
                    "enum": ["markdown", "html", "csv"],
                    "default": "markdown",
                },
                "filename": {"type": "string", "description": "Optional output filename (no ext)"},
            },
            "required": ["run_id"],
        },
    ),
    _handle_testplan_report,
)

registry.register(
    Tool(
        name="cmw_testplan_save",
        description="Save a test plan to JSON (provide 'plan' or a 'run_id').",
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "run_id": {"type": "string"},
                "plan": {"type": "object"},
            },
            "required": ["filename"],
        },
    ),
    _handle_testplan_save,
)

registry.register(
    Tool(
        name="cmw_testplan_load",
        description="Load a saved test plan JSON and return a fresh run_id.",
        inputSchema={
            "type": "object",
            "properties": {"filename": {"type": "string"}},
            "required": ["filename"],
        },
    ),
    _handle_testplan_load,
)

registry.register(
    Tool(
        name="cmw_testplan_list",
        description="List saved test plans in the test-plan directory.",
        inputSchema={"type": "object", "properties": {}},
    ),
    _handle_testplan_list,
)

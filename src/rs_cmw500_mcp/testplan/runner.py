"""Resumable test-plan runner (mirrors coex CoexSweep).

Each step dispatches a registered tool by name, so the engine is domain-agnostic:
any current or future tool is usable as a step with no engine change.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from ..limits import LimitLine
from .models import (
    StepResult,
    TestPlan,
    TestRunResult,
    flatten_numeric,
    get_dotted,
)

_CTX_TOKEN = re.compile(r"\$\{ctx\.([^}]+)\}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _substitute(value: Any, context: dict[str, Any]) -> Any:
    """Replace ${ctx.KEY} tokens using the run context (recursively)."""
    if isinstance(value, str):
        whole = _CTX_TOKEN.fullmatch(value)
        if whole:
            return context.get(whole.group(1), value)
        return _CTX_TOKEN.sub(lambda m: str(context.get(m.group(1), m.group(0))), value)
    if isinstance(value, dict):
        return {k: _substitute(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, context) for v in value]
    return value


class TestRun:
    """Execution state for one test-plan run."""

    __test__ = False  # not a pytest test class

    def __init__(
        self,
        run_id: str,
        plan: TestPlan,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self.run_id = run_id
        self.plan = plan
        self.host = host if host is not None else plan.host
        self.port = port if port is not None else plan.port
        self.cursor = 0
        self.step_results: list[StepResult] = []
        self.context: dict[str, Any] = {}
        self.aborted = False
        self.environment: dict[str, Any] = {}
        self.started_at = _now()
        self.finished_at: str | None = None

    @property
    def total(self) -> int:
        return len(self.plan.steps)

    @property
    def done(self) -> bool:
        return self.cursor >= self.total

    async def _dispatch(self, tool: str, args: dict[str, Any]) -> tuple[bool, Any]:
        """Dispatch a tool; return (is_error, parsed_result)."""
        import json

        from mcp.types import TextContent

        from ..tools.registry import registry

        try:
            res = await registry.dispatch(tool, args)
        except Exception as exc:  # noqa: BLE001 - mirror handle_tool's safety net
            return True, f"{type(exc).__name__}: {exc}"
        text = ""
        if res.content:
            first = res.content[0]
            text = first.text if isinstance(first, TextContent) else str(first)
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            parsed = text
        return bool(res.isError), parsed

    async def step(self, max_steps: int = 1) -> dict[str, Any]:
        """Advance up to ``max_steps`` steps, then return progress."""
        ran = 0
        while ran < max_steps and not self.done:
            step = self.plan.steps[self.cursor]

            # Skip non-teardown steps once aborted (teardown still runs).
            if self.aborted and step.role != "teardown":
                self.step_results.append(
                    StepResult(
                        index=self.cursor,
                        name=step.name,
                        tool=step.tool,
                        role=step.role,
                        status="skipped",
                        started_at=_now(),
                    )
                )
                self.cursor += 1
                ran += 1
                continue

            args = _substitute(dict(step.args), self.context)
            args.setdefault("host", self.host)
            args.setdefault("port", self.port)
            # Drop null host/port so tools fall back to settings/profile defaults.
            args = {k: v for k, v in args.items() if not (k in ("host", "port") and v is None)}

            started = _now()
            t0 = time.monotonic()
            is_error, parsed = await self._dispatch(step.tool, args)
            duration = time.monotonic() - t0

            measurements: dict[str, float] = {}
            limit_result: dict[str, Any] | None = None
            note: str | None = None
            error: str | None = None

            if is_error:
                status = "error"
                error = parsed if isinstance(parsed, str) else str(parsed)
            else:
                # Save context values from this step's result.
                for result_path, ctx_key in step.save_as.items():
                    val = get_dotted(parsed, result_path)
                    if val is not None:
                        self.context[ctx_key] = val

                if step.limits:
                    flat = flatten_numeric(parsed)
                    checked = [c.parameter for c in step.limits]
                    measurements = {p: flat[p] for p in checked if p in flat}
                    line = LimitLine(name=step.name, segments=[c.to_segment() for c in step.limits])
                    lr = line.check(flat)
                    limit_result = lr.to_dict()
                    missing = [p for p in checked if p not in flat]
                    if missing:
                        status = "fail"
                        note = f"limit parameters not found in result: {missing}"
                    else:
                        status = "pass" if lr.passed else "fail"
                else:
                    status = "pass"

            self.step_results.append(
                StepResult(
                    index=self.cursor,
                    name=step.name,
                    tool=step.tool,
                    role=step.role,
                    status=status,
                    is_error=is_error,
                    result=parsed,
                    measurements=measurements,
                    limit_result=limit_result,
                    started_at=started,
                    duration_s=duration,
                    error=error,
                    note=note,
                )
            )

            if (status == "fail" and step.abort_on_fail) or (
                is_error and not step.continue_on_error
            ):
                self.aborted = True

            self.cursor += 1
            ran += 1

        if self.done and self.finished_at is None:
            self.finished_at = _now()
        return self.result(include_results=False)

    async def run(self) -> dict[str, Any]:
        """Drain all remaining steps (unattended)."""
        while not self.done:
            await self.step(max_steps=self.total)
        return self.result(include_results=False)

    def _counts(self) -> dict[str, int]:
        c = {"passed": 0, "failed": 0, "errored": 0, "skipped": 0}
        for s in self.step_results:
            if s.status == "pass":
                c["passed"] += 1
            elif s.status == "fail":
                c["failed"] += 1
            elif s.status == "error":
                c["errored"] += 1
            elif s.status == "skipped":
                c["skipped"] += 1
        return c

    def _status(self) -> str:
        if not self.done:
            return "running"
        return "aborted" if self.aborted else "complete"

    def result(self, include_results: bool = True) -> dict[str, Any]:
        counts = self._counts()
        data: dict[str, Any] = {
            "run_id": self.run_id,
            "plan_name": self.plan.name,
            "status": self._status(),
            "progress": {
                "done": self.cursor,
                "total": self.total,
                "percent": round(100.0 * self.cursor / self.total, 1) if self.total else 100.0,
            },
            "summary": {"total_steps": self.total, **counts, "aborted": self.aborted},
        }
        if include_results:
            data["steps"] = [s.to_dict() for s in self.step_results]
        return data

    def to_run_result(self) -> TestRunResult:
        counts = self._counts()
        return TestRunResult(
            run_id=self.run_id,
            plan_name=self.plan.name,
            status=self._status(),
            started_at=self.started_at,
            finished_at=self.finished_at,
            total_steps=self.total,
            passed=counts["passed"],
            failed=counts["failed"],
            errored=counts["errored"],
            skipped=counts["skipped"],
            aborted=self.aborted,
            steps=list(self.step_results),
            environment=self.environment,
        )

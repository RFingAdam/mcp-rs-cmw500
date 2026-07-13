"""Test-plan data models + numeric extraction for limit checking."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..limits import LimitSegment

VALID_ROLES = ("setup", "main", "teardown")


def flatten_numeric(obj: Any, prefix: str = "") -> dict[str, float]:
    """Flatten a nested tool result into dotted-path -> float.

    Walks dicts (dotted keys) and lists (index keys). Keeps ints/floats and
    float-parsable strings; skips bools. Enables limit checks against nested
    results like ``lte_meas_fetch_all`` via paths such as ``power.current_dbm``.
    """
    out: dict[str, float] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten_numeric(value, child))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            child = f"{prefix}.{i}" if prefix else str(i)
            out.update(flatten_numeric(value, child))
    elif isinstance(obj, bool):
        return out  # skip booleans (bool is an int subclass)
    elif isinstance(obj, (int, float)):
        out[prefix] = float(obj)
    elif isinstance(obj, str):
        try:
            out[prefix] = float(obj)
        except ValueError:
            pass
    return out


def get_dotted(obj: Any, path: str) -> Any:
    """Navigate a nested dict/list by a dotted path (list indices as ints)."""
    current = obj
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


@dataclass
class LimitCheck:
    """A pass/fail limit on one dotted result path."""

    parameter: str  # dotted path into the step result, e.g. "power.current_dbm"
    max_value: float | None = None
    min_value: float | None = None
    unit: str = ""

    def to_segment(self) -> LimitSegment:
        return LimitSegment(
            parameter=self.parameter,
            max_value=self.max_value,
            min_value=self.min_value,
            unit=self.unit,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameter": self.parameter,
            "max_value": self.max_value,
            "min_value": self.min_value,
            "unit": self.unit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LimitCheck:
        return cls(
            parameter=data["parameter"],
            max_value=data.get("max_value"),
            min_value=data.get("min_value"),
            unit=data.get("unit", ""),
        )


@dataclass
class TestStep:
    """One step: invoke a registered tool, optionally check limits."""

    __test__ = False  # not a pytest test class

    name: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    limits: list[LimitCheck] = field(default_factory=list)
    role: str = "main"  # setup | main | teardown
    abort_on_fail: bool = False
    continue_on_error: bool = True
    save_as: dict[str, str] = field(default_factory=dict)  # result path -> context key

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tool": self.tool,
            "args": self.args,
            "limits": [c.to_dict() for c in self.limits],
            "role": self.role,
            "abort_on_fail": self.abort_on_fail,
            "continue_on_error": self.continue_on_error,
            "save_as": self.save_as,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestStep:
        role = data.get("role", "main")
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid step role {role!r}; must be one of {VALID_ROLES}")
        return cls(
            name=data["name"],
            tool=data["tool"],
            args=data.get("args", {}),
            limits=[LimitCheck.from_dict(c) for c in data.get("limits", [])],
            role=role,
            abort_on_fail=data.get("abort_on_fail", False),
            continue_on_error=data.get("continue_on_error", True),
            save_as=data.get("save_as", {}),
        )


@dataclass
class TestPlan:
    """An ordered list of steps with optional default host/port."""

    __test__ = False  # not a pytest test class

    name: str
    steps: list[TestStep]
    description: str = ""
    host: str | None = None
    port: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "host": self.host,
            "port": self.port,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestPlan:
        return cls(
            name=data["name"],
            steps=[TestStep.from_dict(s) for s in data.get("steps", [])],
            description=data.get("description", ""),
            host=data.get("host"),
            port=data.get("port"),
        )

    def save(self, filepath: str | Path) -> None:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, filepath: str | Path) -> TestPlan:
        return cls.from_dict(json.loads(Path(filepath).read_text(encoding="utf-8")))


@dataclass
class StepResult:
    """Outcome of one executed step."""

    index: int
    name: str
    tool: str
    role: str
    status: str  # pass | fail | error | skipped
    is_error: bool = False
    result: Any = None
    measurements: dict[str, float] = field(default_factory=dict)
    limit_result: dict[str, Any] | None = None
    started_at: str = ""
    duration_s: float = 0.0
    error: str | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "index": self.index,
            "name": self.name,
            "tool": self.tool,
            "role": self.role,
            "status": self.status,
            "is_error": self.is_error,
            "duration_s": round(self.duration_s, 3),
        }
        if self.started_at:
            data["started_at"] = self.started_at
        if self.measurements:
            data["measurements"] = self.measurements
        if self.limit_result is not None:
            data["limit_result"] = self.limit_result
        if self.error:
            data["error"] = self.error
        if self.note:
            data["note"] = self.note
        if self.result is not None:
            data["result"] = self.result
        return data


@dataclass
class TestRunResult:
    """Full run outcome — the report source-of-truth."""

    __test__ = False  # not a pytest test class

    run_id: str
    plan_name: str
    status: str  # running | complete | aborted
    started_at: str = ""
    finished_at: str | None = None
    total_steps: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    skipped: int = 0
    aborted: bool = False
    steps: list[StepResult] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)

    @property
    def overall_passed(self) -> bool:
        return self.failed == 0 and self.errored == 0 and not self.aborted

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "plan_name": self.plan_name,
            "status": self.status,
            "overall_passed": self.overall_passed,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "summary": {
                "total_steps": self.total_steps,
                "passed": self.passed,
                "failed": self.failed,
                "errored": self.errored,
                "skipped": self.skipped,
                "aborted": self.aborted,
            },
            "environment": self.environment,
            "steps": [s.to_dict() for s in self.steps],
        }

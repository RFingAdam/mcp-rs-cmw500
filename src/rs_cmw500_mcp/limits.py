"""Pass/fail limit testing for CMW500 measurements."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class LimitFailure:
    """Details of a single limit violation."""

    parameter: str
    measured_value: float
    limit_value: float
    limit_type: str  # "max" or "min"
    unit: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "parameter": self.parameter,
            "measured_value": self.measured_value,
            "limit_value": self.limit_value,
            "limit_type": self.limit_type,
            "unit": self.unit,
            "violation": abs(self.measured_value - self.limit_value),
        }


@dataclass
class LimitSegment:
    """
    Single parameter limit definition.

    Defines upper and/or lower limits for a measurement parameter.
    Either max_value or min_value (or both) must be specified.
    """

    parameter: str
    max_value: float | None = None
    min_value: float | None = None
    unit: str = ""
    name: str | None = None

    def __post_init__(self) -> None:
        """Validate segment configuration."""
        if self.max_value is None and self.min_value is None:
            raise ValueError("LimitSegment must have at least max_value or min_value specified")

    def check_value(self, measured: float) -> LimitFailure | None:
        """
        Check if a measured value passes the limit.

        Args:
            measured: Measured value

        Returns:
            LimitFailure if limit violated, None if pass
        """
        if self.max_value is not None and measured > self.max_value:
            return LimitFailure(
                parameter=self.parameter,
                measured_value=measured,
                limit_value=self.max_value,
                limit_type="max",
                unit=self.unit,
            )

        if self.min_value is not None and measured < self.min_value:
            return LimitFailure(
                parameter=self.parameter,
                measured_value=measured,
                limit_value=self.min_value,
                limit_type="min",
                unit=self.unit,
            )

        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "parameter": self.parameter,
            "max_value": self.max_value,
            "min_value": self.min_value,
            "unit": self.unit,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LimitSegment":
        """Create from dictionary."""
        return cls(
            parameter=data["parameter"],
            max_value=data.get("max_value"),
            min_value=data.get("min_value"),
            unit=data.get("unit", ""),
            name=data.get("name"),
        )


@dataclass
class LimitResult:
    """
    Result of limit checking.

    Contains pass/fail status and details of any violations.
    """

    passed: bool
    failures: list[LimitFailure]
    total_checks: int
    failed_checks: int
    worst_failure: LimitFailure | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "passed": self.passed,
            "total_checks": self.total_checks,
            "failed_checks": self.failed_checks,
            "pass_rate": (self.total_checks - self.failed_checks) / self.total_checks
            if self.total_checks > 0
            else 0,
        }

        if self.worst_failure:
            result["worst_failure"] = self.worst_failure.to_dict()

        if self.failures:
            result["failure_count"] = len(self.failures)
            result["failures"] = [f.to_dict() for f in self.failures[:10]]
            if len(self.failures) > 10:
                result["additional_failures"] = len(self.failures) - 10

        return result


@dataclass
class LimitLine:
    """
    Complete limit line definition for CMW500 measurements.

    A limit line consists of one or more segments that define
    pass/fail criteria for measurement parameters.
    """

    name: str
    segments: list[LimitSegment]
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def check(self, measurements: dict[str, float]) -> LimitResult:
        """
        Check measurement data against all limit segments.

        Args:
            measurements: Dictionary mapping parameter names to measured values

        Returns:
            LimitResult with pass/fail status and details
        """
        failures: list[LimitFailure] = []
        total_checks = 0

        for segment in self.segments:
            if segment.parameter in measurements:
                total_checks += 1
                failure = segment.check_value(measurements[segment.parameter])
                if failure:
                    failures.append(failure)

        worst = None
        if failures:
            worst = max(failures, key=lambda f: abs(f.measured_value - f.limit_value))

        return LimitResult(
            passed=len(failures) == 0,
            failures=failures,
            total_checks=total_checks,
            failed_checks=len(failures),
            worst_failure=worst,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "segments": [s.to_dict() for s in self.segments],
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LimitLine":
        """Create from dictionary."""
        segments = [LimitSegment.from_dict(s) for s in data["segments"]]

        created_at = datetime.now()
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except ValueError:
                pass

        return cls(
            name=data["name"],
            segments=segments,
            description=data.get("description", ""),
            created_at=created_at,
        )

    def save(self, filepath: str | Path) -> None:
        """Save limit line to JSON file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str | Path) -> "LimitLine":
        """Load limit line from JSON file."""
        with open(filepath) as f:
            data = json.load(f)
        return cls.from_dict(data)


class LimitManager:
    """
    Manages limit line definitions for a testing session.

    Provides storage and retrieval of limit lines, and batch
    checking of measurements against multiple limits.
    """

    def __init__(self) -> None:
        """Initialize limit manager."""
        self._limits: dict[str, LimitLine] = {}

    def add_limit(self, limit: LimitLine) -> None:
        """Add or update a limit line."""
        self._limits[limit.name] = limit

    def remove_limit(self, name: str) -> bool:
        """Remove a limit line by name."""
        if name in self._limits:
            del self._limits[name]
            return True
        return False

    def get_limit(self, name: str) -> LimitLine | None:
        """Get a limit line by name."""
        return self._limits.get(name)

    def list_limits(self) -> list[str]:
        """List all limit line names."""
        return list(self._limits.keys())

    def clear_limits(self) -> None:
        """Remove all limit lines."""
        self._limits.clear()

    def check_all(self, measurements: dict[str, float]) -> dict[str, LimitResult]:
        """
        Check measurements against all defined limits.

        Args:
            measurements: Dictionary mapping parameter names to values

        Returns:
            Dictionary mapping limit name to result
        """
        results = {}
        for name, limit in self._limits.items():
            results[name] = limit.check(measurements)
        return results

    def get_overall_status(self, measurements: dict[str, float]) -> dict[str, Any]:
        """
        Get overall pass/fail status across all limits.

        Args:
            measurements: Dictionary mapping parameter names to values

        Returns:
            Dictionary with overall status and per-limit results
        """
        results = self.check_all(measurements)
        all_passed = all(r.passed for r in results.values()) if results else True

        return {
            "overall_passed": all_passed,
            "limits_checked": len(results),
            "limits_passed": sum(1 for r in results.values() if r.passed),
            "limits_failed": sum(1 for r in results.values() if not r.passed),
            "results": {name: result.to_dict() for name, result in results.items()},
        }

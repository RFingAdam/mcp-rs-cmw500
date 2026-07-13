"""Test-plan + reporting engine.

A TestPlan is an ordered list of TestSteps. Each step invokes ANY registered MCP
tool by name (via the tool registry), optionally applies pass/fail limit checks
to the step's numeric results, and records the outcome. Runs are resumable
(mirroring the coex sweep). Reports render to Markdown / self-contained HTML / CSV.
"""

from .models import (
    LimitCheck,
    StepResult,
    TestPlan,
    TestRunResult,
    TestStep,
    flatten_numeric,
)
from .report import render_csv, render_html, render_markdown
from .runner import TestRun

__all__ = [
    "LimitCheck",
    "StepResult",
    "TestPlan",
    "TestRunResult",
    "TestStep",
    "flatten_numeric",
    "render_csv",
    "render_html",
    "render_markdown",
    "TestRun",
]

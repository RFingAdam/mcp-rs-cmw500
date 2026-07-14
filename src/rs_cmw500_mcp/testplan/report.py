"""Render a TestRunResult to Markdown, self-contained HTML, or CSV.

String templating only — no third-party dependencies. (PDF is intentionally out
of scope; open the HTML and print-to-PDF in a browser.)
"""

from __future__ import annotations

import csv
import html
import io
import json

from .models import TestRunResult

_VERDICT = {"pass": "PASS", "fail": "FAIL", "error": "ERROR", "skipped": "SKIP"}


def _overall(rr: TestRunResult) -> str:
    return "PASS" if rr.overall_passed else "FAIL"


def render_markdown(rr: TestRunResult) -> str:
    lines: list[str] = []
    lines.append(f"# Test report: {rr.plan_name}")
    lines.append("")
    lines.append(f"**Overall: {_overall(rr)}** — status `{rr.status}`")
    lines.append(f"- Run ID: `{rr.run_id}`")
    lines.append(f"- Started: {rr.started_at}  Finished: {rr.finished_at or '-'}")
    lines.append(
        f"- Steps: {rr.total_steps} — pass {rr.passed}, fail {rr.failed}, "
        f"error {rr.errored}, skipped {rr.skipped}"
    )
    if rr.environment:
        env = ", ".join(f"{k}={v}" for k, v in rr.environment.items())
        lines.append(f"- Environment: {env}")
    lines.append("")
    lines.append("| # | Step | Tool | Role | Verdict | Detail |")
    lines.append("|---|------|------|------|---------|--------|")
    for s in rr.steps:
        detail = s.error or s.note or ""
        if s.limit_result and not detail:
            lr = s.limit_result
            detail = f"{lr.get('failed_checks', 0)}/{lr.get('total_checks', 0)} failed"
        detail = detail.replace("|", "\\|")
        lines.append(
            f"| {s.index} | {s.name} | `{s.tool}` | {s.role} | "
            f"{_VERDICT.get(s.status, s.status)} | {detail} |"
        )
    lines.append("")
    # Per-step measurement detail for checked limits.
    for s in rr.steps:
        if s.measurements:
            lines.append(f"### Step {s.index}: {s.name}")
            lines.append("")
            lines.append("| Parameter | Measured |")
            lines.append("|-----------|----------|")
            for param, val in s.measurements.items():
                lines.append(f"| {param} | {val} |")
            lines.append("")
    return "\n".join(lines)


def render_csv(rr: TestRunResult) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["run_id", "step_index", "step", "tool", "role", "verdict", "parameter", "measured"]
    )
    for s in rr.steps:
        verdict = _VERDICT.get(s.status, s.status)
        if s.measurements:
            for param, val in s.measurements.items():
                writer.writerow([rr.run_id, s.index, s.name, s.tool, s.role, verdict, param, val])
        else:
            writer.writerow([rr.run_id, s.index, s.name, s.tool, s.role, verdict, "", ""])
    return buf.getvalue()


_HTML_STYLE = """
body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:2rem;color:#111;background:#fff}
h1{margin-bottom:.2rem}
.banner{display:inline-block;padding:.3rem .8rem;border-radius:.4rem;font-weight:700;color:#fff}
.pass{background:#1a7f37}.fail{background:#c11}
table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{border:1px solid #ccc;padding:.4rem .6rem;text-align:left;font-size:.9rem}
th{background:#f2f2f2}
tr.v-fail td,tr.v-error td{background:#fde8e8}
tr.v-pass td{background:#eafaef}
tr.v-skipped td{background:#f4f4f4;color:#666}
details{margin:.3rem 0}code{background:#f4f4f4;padding:0 .2rem;border-radius:.2rem}
.meta{color:#444;font-size:.9rem}
"""


def render_html(rr: TestRunResult) -> str:
    banner = "pass" if rr.overall_passed else "fail"
    rows: list[str] = []
    for s in rr.steps:
        detail = s.error or s.note or ""
        if s.limit_result and not detail:
            lr = s.limit_result
            detail = f"{lr.get('failed_checks', 0)}/{lr.get('total_checks', 0)} limit(s) failed"
        result_json = html.escape(json.dumps(s.result, indent=2, default=str))
        rows.append(
            f'<tr class="v-{s.status}"><td>{s.index}</td>'
            f"<td>{html.escape(s.name)}</td><td><code>{html.escape(s.tool)}</code></td>"
            f"<td>{s.role}</td><td>{_VERDICT.get(s.status, s.status)}</td>"
            f"<td>{html.escape(detail)}"
            f"<details><summary>result</summary><pre>{result_json}</pre></details></td></tr>"
        )
    env = html.escape(", ".join(f"{k}={v}" for k, v in rr.environment.items()))
    title = html.escape(rr.plan_name)
    counts = (
        f"Steps: {rr.total_steps} — pass {rr.passed}, fail {rr.failed}, "
        f"error {rr.errored}, skipped {rr.skipped}"
    )
    meta = (
        f'<p class="meta">Run <code>{rr.run_id}</code> · started {rr.started_at} · '
        f"finished {rr.finished_at or '-'}<br>{counts}<br>"
        f"{('Environment: ' + env) if env else ''}</p>"
    )
    thead = (
        "<tr><th>#</th><th>Step</th><th>Tool</th><th>Role</th><th>Verdict</th><th>Detail</th></tr>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Test report: {title}</title>
<style>{_HTML_STYLE}</style></head><body>
<h1>Test report: {title}</h1>
<p><span class="banner {banner}">{_overall(rr)}</span> &nbsp; status: <code>{rr.status}</code></p>
{meta}
<table><thead>{thead}</thead>
<tbody>{"".join(rows)}</tbody></table>
</body></html>
"""

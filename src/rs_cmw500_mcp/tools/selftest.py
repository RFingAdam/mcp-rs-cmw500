"""Bench self-test: identify the unit, list licensed domains, non-destructive smoke.

Run on real hardware after setup to confirm which licensed domains are live. All
probes are read-only (state/route queries) — no cell/AP/generator is switched on.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.types import CallToolResult, Tool

from ..driver.cmw500_driver import CMW500Driver
from ..licensing import domains_for_options
from ..profile import get_active_profile
from .registry import registry
from .shared import _format_error, _format_result, _get_cmw

logger = logging.getLogger(__name__)

# Read-only smoke probes per domain (query/state only — never switch anything on).
_PROBES: dict[str, Callable[[CMW500Driver], Awaitable[str]]] = {
    "lte_signaling": lambda c: c.lte_sig_cell_state_all(),
    "wlan_signaling": lambda c: c.wlan_sig_state_all(),
    "gsm_signaling": lambda c: c.gsm_sig_state_all(),
    "wcdma_signaling": lambda c: c.wcdma_sig_state_all(),
    "gprf": lambda c: c.get_signal_path(),
}


async def _handle_selftest(args: dict[str, Any]) -> CallToolResult:
    try:
        cmw = await _get_cmw(args.get("host"), args.get("port"))
    except Exception as exc:  # noqa: BLE001 - report offline gracefully
        return _format_error(exc)

    info = await cmw.identify()
    options = await cmw.query_options()
    licensed = domains_for_options(options)

    run_smoke = bool(args.get("run_smoke", True))
    domains: dict[str, dict[str, Any]] = {}
    for domain, is_licensed in licensed.items():
        entry: dict[str, Any] = {"licensed": is_licensed, "smoke_ok": None}
        if is_licensed and run_smoke and domain in _PROBES:
            try:
                await _PROBES[domain](cmw)
                entry["smoke_ok"] = True
            except Exception as exc:  # noqa: BLE001 - probe failure is informative
                entry["smoke_ok"] = False
                entry["note"] = str(exc)
        domains[domain] = entry

    profile = get_active_profile()
    expected_vs_actual: dict[str, Any] | None = None
    if profile and profile.expected_licenses:
        upper = [o.upper() for o in options]
        missing = [e for e in profile.expected_licenses if not any(e.upper() in o for o in upper)]
        expected_vs_actual = {
            "expected": profile.expected_licenses,
            "missing": missing,
            "ok": not missing,
        }

    return _format_result(
        {
            "instrument": info.to_dict(),
            "options": options,
            "domains": domains,
            "expected_vs_actual": expected_vs_actual,
        }
    )


registry.register(
    Tool(
        name="cmw_selftest",
        description=(
            "Connect, identify (*IDN?), list installed options (*OPT?), and run a "
            "read-only smoke check per licensed domain. Reports which domains are "
            "live. Non-destructive: switches nothing on. Run after bench setup."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "run_smoke": {"type": "boolean", "default": True},
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_selftest,
)

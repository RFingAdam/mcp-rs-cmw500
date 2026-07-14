"""LTE receiver-sensitivity (Extended BLER / EBL) tools for the CMW500.

Adds the RX side the server previously lacked: cell attach lifecycle, single
Extended-BLER measurements, and an orchestrated coarse+fine sensitivity search.
The reusable coroutines (`wait_for_lte_attach`, `run_lte_rx_sensitivity`) are
imported by the coexistence orchestrator as well as exposed as MCP tools.
"""

import asyncio
import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from ..driver.cmw500_driver import CMW500Driver
from ..driver.search import descend_to_threshold
from ..exceptions import CMW500Error
from ..models.band_plans import earfcn_to_frequencies
from ..models.cmw_types import LTEBandwidth, RxSensitivityResult
from .registry import registry
from .shared import _format_result, _get_cmw

logger = logging.getLogger(__name__)

DEFAULT_COARSE_DELAY_S = 0.15
DEFAULT_FINE_DELAY_S = 0.55


async def wait_for_lte_attach(
    cmw: CMW500Driver,
    timeout_s: float = 90.0,
    adj_timeout_s: float = 20.0,
    cell_off_reset_s: float = 12.0,
    max_retries: int = 2,
) -> tuple[bool, str]:
    """Bring the cell up and wait for UE attach, with staged cell-OFF resets.

    Returns (attached, last_state). Mirrors the validated attach lifecycle:
    cell ON -> wait for 'ON,ADJ' -> poll PS state for 'ATT'; on timeout, hold the
    cell OFF to force the UE idle, then retry.
    """
    loop = asyncio.get_event_loop()
    attempt = 1
    last_state = ""
    while True:
        await cmw.lte_sig_set_cell_state(True)
        start = loop.time()

        # 1. Wait for the cell to report ON and adjusted (signal stable).
        while loop.time() - start < adj_timeout_s:
            try:
                if "ON,ADJ" in (await cmw.lte_sig_cell_state_all()):
                    break
            except CMW500Error:
                pass
            await asyncio.sleep(1)

        # 2. Poll the packet-switched state for attach.
        while loop.time() - start < timeout_s:
            try:
                last_state = (await cmw.lte_ps_state()).strip()
                if "ATT" in last_state:
                    return True, last_state
            except CMW500Error:
                pass
            await asyncio.sleep(1)

        # 3. Timeout: hold cell OFF to reset the UE, then retry.
        await cmw.lte_sig_set_cell_state(False)
        if attempt <= max_retries:
            await asyncio.sleep(cell_off_reset_s)
            attempt += 1
        else:
            return False, last_state


async def run_lte_rx_sensitivity(
    cmw: CMW500Driver,
    earfcn: int,
    start_level: float = -110.0,
    coarse_step: float = 1.0,
    fine_step: float = 0.1,
    target_pct: float = 10.0,
    coarse_subframes: int = 100,
    fine_subframes: int = 500,
    level_floor: float = -125.0,
    level_ceiling: float = -50.0,
    coarse_delay_s: float = DEFAULT_COARSE_DELAY_S,
    fine_delay_s: float = DEFAULT_FINE_DELAY_S,
    fetch_retries: int = 20,
) -> RxSensitivityResult:
    """Find the DL RS-EPRE level at the target BLER for one EARFCN.

    Uses the shared coarse+fine search: a coarse pass (fewer subframes) climbs to
    a passing level then descends; a fine pass (more subframes) refines the
    crossing. Sensitivity is the lowest RS-EPRE level still below ``target_pct``.
    """
    await cmw.lte_set_earfcn(earfcn, "DL")
    delay = {"s": coarse_delay_s}

    async def on_coarse_start() -> None:
        await cmw.lte_ebl_configure(coarse_subframes, single_shot=True)

    async def on_fine_start() -> None:
        await cmw.lte_ebl_set_subframes(fine_subframes)
        delay["s"] = fine_delay_s

    async def measure(level: float) -> float | None:
        await cmw.lte_set_rsepre_level(level)
        await cmw.lte_ebl_init()
        await asyncio.sleep(delay["s"])
        current = delay["s"]
        for _ in range(fetch_retries):
            result = await cmw.lte_ebl_fetch()
            if result.dropped:
                return None
            if result.bler_percent is not None:
                return result.bler_percent
            current = round(current + 0.05, 2)
            await asyncio.sleep(current)
        return None

    search = await descend_to_threshold(
        measure,
        start_level=start_level,
        coarse_step=coarse_step,
        fine_step=fine_step,
        target_pct=target_pct,
        level_floor=level_floor,
        level_ceiling=level_ceiling,
        ascend_first=True,
        on_coarse_start=on_coarse_start,
        on_fine_start=on_fine_start,
    )
    _band, dl_mhz, _ul_mhz = earfcn_to_frequencies(earfcn)
    return RxSensitivityResult(
        technology="LTE-BLER",
        status=search.status,
        sensitivity_dbm=search.threshold_level,
        target_pct=target_pct,
        channel=earfcn,
        frequency_mhz=dl_mhz,
        points_measured=len(search.trace),
        trace=[p.to_dict() for p in search.trace],
    )


# =============================================================================
# Handlers
# =============================================================================


async def _handle_lte_rx_configure(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    band = int(args["band"])
    bw = LTEBandwidth.from_mhz(args.get("bandwidth_mhz", 5.0))
    dl_level = float(args.get("dl_level_dbm", -90.0))
    await cmw.lte_sig_set_cell_state(False)
    await cmw.lte_set_operating_band(band)
    await cmw.lte_set_rx_bandwidth(bw)
    await cmw.lte_set_rsepre_level(dl_level)
    await cmw.lte_ebl_configure(subframes=int(args.get("subframes", 100)), single_shot=True)
    return _format_result(
        {
            "status": "ok",
            "band": band,
            "bandwidth_mhz": bw.mhz,
            "dl_rsepre_dbm": dl_level,
        }
    )


async def _handle_lte_attach_wait(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    attached, state = await wait_for_lte_attach(
        cmw,
        timeout_s=float(args.get("timeout_s", 90.0)),
        adj_timeout_s=float(args.get("adj_timeout_s", 20.0)),
        cell_off_reset_s=float(args.get("cell_off_reset_s", 12.0)),
        max_retries=int(args.get("max_retries", 2)),
    )
    return _format_result({"attached": attached, "state": state})


async def _handle_lte_rx_measure_bler(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.lte_ebl_set_subframes(int(args.get("subframes", 100)))
    await cmw.lte_set_rsepre_level(float(args["level_dbm"]))
    await cmw.lte_ebl_init()
    await asyncio.sleep(float(args.get("delay_s", DEFAULT_COARSE_DELAY_S)))
    result = await cmw.lte_ebl_fetch()
    return _format_result({"level_dbm": float(args["level_dbm"]), **result.to_dict()})


async def _handle_lte_rx_sensitivity(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await run_lte_rx_sensitivity(
        cmw,
        earfcn=int(args["earfcn"]),
        start_level=float(args.get("start_level_dbm", -110.0)),
        coarse_step=float(args.get("coarse_step_db", 1.0)),
        fine_step=float(args.get("fine_step_db", 0.1)),
        target_pct=float(args.get("target_bler_pct", 10.0)),
        coarse_subframes=int(args.get("coarse_subframes", 100)),
        fine_subframes=int(args.get("fine_subframes", 500)),
    )
    return _format_result(result.to_dict())


# =============================================================================
# Registration
# =============================================================================

_HOST_PORT = {"host": {"type": "string"}, "port": {"type": "integer"}}

registry.register(
    Tool(
        name="cmw_lte_rx_configure",
        description=(
            "Configure the LTE cell for receiver-sensitivity (Extended BLER) "
            "testing: operating band, DL bandwidth, DL RS-EPRE level, single-shot "
            "EBL. Call before cmw_lte_attach_wait."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "band": {"type": "integer", "description": "LTE operating band (e.g. 7)"},
                "bandwidth_mhz": {
                    "type": "number",
                    "enum": [1.4, 3, 5, 10, 15, 20],
                    "description": "DL cell bandwidth in MHz (default 5)",
                    "default": 5,
                },
                "dl_level_dbm": {
                    "type": "number",
                    "description": "DL RS-EPRE level (dBm/15kHz) for attach (default -90)",
                    "default": -90,
                },
                "subframes": {
                    "type": "integer",
                    "description": "Coarse EBL subframe count (default 100)",
                    "default": 100,
                },
                **_HOST_PORT,
            },
            "required": ["band"],
        },
    ),
    _handle_lte_rx_configure,
)

registry.register(
    Tool(
        name="cmw_lte_attach_wait",
        description=(
            "Turn the cell on and wait for the UE to attach, with staged cell-OFF "
            "resets and retries. Returns whether attach succeeded."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "timeout_s": {"type": "number", "default": 90},
                "adj_timeout_s": {"type": "number", "default": 20},
                "cell_off_reset_s": {"type": "number", "default": 12},
                "max_retries": {"type": "integer", "default": 2},
                **_HOST_PORT,
            },
        },
    ),
    _handle_lte_attach_wait,
)

registry.register(
    Tool(
        name="cmw_lte_rx_measure_bler",
        description=(
            "Run a single Extended-BLER measurement at a given DL RS-EPRE level and "
            "return reliability + BLER %. Reliability 19 means the call dropped."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "level_dbm": {
                    "type": "number",
                    "description": "DL RS-EPRE level (dBm/15kHz)",
                },
                "subframes": {"type": "integer", "default": 100},
                "delay_s": {
                    "type": "number",
                    "description": "Settle time before fetch (default 0.15)",
                    "default": 0.15,
                },
                **_HOST_PORT,
            },
            "required": ["level_dbm"],
        },
    ),
    _handle_lte_rx_measure_bler,
)

registry.register(
    Tool(
        name="cmw_lte_rx_sensitivity",
        description=(
            "Find LTE receiver sensitivity at one EARFCN: a coarse+fine search for "
            "the lowest DL RS-EPRE level meeting the target BLER (default 10%). "
            "Requires the UE to be attached (see cmw_lte_attach_wait)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "earfcn": {"type": "integer", "description": "DL EARFCN to test"},
                "start_level_dbm": {"type": "number", "default": -110},
                "coarse_step_db": {"type": "number", "default": 1.0},
                "fine_step_db": {"type": "number", "default": 0.1},
                "target_bler_pct": {"type": "number", "default": 10.0},
                "coarse_subframes": {"type": "integer", "default": 100},
                "fine_subframes": {"type": "integer", "default": 500},
                **_HOST_PORT,
            },
            "required": ["earfcn"],
        },
    ),
    _handle_lte_rx_sensitivity,
)

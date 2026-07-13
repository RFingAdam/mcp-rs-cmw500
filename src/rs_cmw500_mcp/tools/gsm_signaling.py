"""GSM/GPRS signaling tools (options CMW-KS200/KM200; app-note-derived).

Gate on cmw_query_options; validate on hardware.
"""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from .registry import registry
from .shared import _format_result, _get_cmw

logger = logging.getLogger(__name__)

_HOST_PORT = {"host": {"type": "string"}, "port": {"type": "integer"}}


async def _handle_gsm_sig_configure(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    band = args.get("band", "G09")
    await cmw.gsm_sig_set_band(band)
    if args.get("arfcn") is not None:
        await cmw.gsm_sig_set_arfcn(int(args["arfcn"]), "TCH")
    await cmw.gsm_sig_set_level(float(args.get("level_dbm", -60.0)))
    return _format_result({"status": "ok", "band": band, "arfcn": args.get("arfcn")})


async def _handle_gsm_sig_cell_on(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.gsm_sig_set_state(True)
    return _format_result({"status": "ok", "cell": "ON"})


async def _handle_gsm_sig_cell_off(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.gsm_sig_set_state(False)
    return _format_result({"status": "ok", "cell": "OFF"})


async def _handle_gsm_sig_get_state(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    return _format_result(
        {
            "cell_state": (await cmw.gsm_sig_state_all()).strip(),
            "connection_state": (await cmw.gsm_sig_connection_state()).strip(),
        }
    )


async def _handle_gsm_meas_tx(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.gsm_meas_configure(stat_count=int(args.get("stat_count", 10)))
    await cmw.gsm_meas_init()
    result = await cmw.gsm_meas_fetch_power()
    return _format_result(result.to_dict())


async def _handle_gsm_sig_ber(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.gsm_sig_fetch_ber()
    return _format_result(result.to_dict())


registry.register(
    Tool(
        name="cmw_gsm_sig_configure",
        description=(
            "Configure a GSM signaling cell (band, ARFCN, level). Requires GSM "
            "signaling license; app-note-derived - validate on hardware."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "band": {"type": "string", "description": "CMW GSM band token (e.g. G09, G18)"},
                "arfcn": {"type": "integer", "description": "TCH ARFCN"},
                "level_dbm": {"type": "number", "default": -60},
                **_HOST_PORT,
            },
        },
    ),
    _handle_gsm_sig_configure,
)

registry.register(
    Tool(
        name="cmw_gsm_sig_cell_on",
        description="Turn the GSM signaling cell on.",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_gsm_sig_cell_on,
)

registry.register(
    Tool(
        name="cmw_gsm_sig_cell_off",
        description="Turn the GSM signaling cell off.",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_gsm_sig_cell_off,
)

registry.register(
    Tool(
        name="cmw_gsm_sig_get_state",
        description="Read GSM cell state and circuit-switched connection state.",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_gsm_sig_get_state,
)

registry.register(
    Tool(
        name="cmw_gsm_meas_tx",
        description="Configure + trigger + fetch GSM TX burst power (MEValuation).",
        inputSchema={
            "type": "object",
            "properties": {"stat_count": {"type": "integer", "default": 10}, **_HOST_PORT},
        },
    ),
    _handle_gsm_meas_tx,
)

registry.register(
    Tool(
        name="cmw_gsm_sig_ber",
        description="Fetch GSM RX BER (reliability + BER%).",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_gsm_sig_ber,
)

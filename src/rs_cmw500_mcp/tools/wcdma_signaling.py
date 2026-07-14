"""WCDMA/UMTS signaling tools (options CMW-KS400/KM400; app-note-derived).

Gate on cmw_query_options; validate on hardware.
"""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from .registry import registry
from .shared import _format_result, _get_cmw

logger = logging.getLogger(__name__)

_HOST_PORT = {"host": {"type": "string"}, "port": {"type": "integer"}}


async def _handle_wcdma_sig_configure(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    band = args.get("band", "OB1")
    await cmw.wcdma_sig_set_band(band)
    if args.get("dl_channel") is not None:
        await cmw.wcdma_sig_set_dl_channel(int(args["dl_channel"]))
    await cmw.wcdma_sig_set_level(float(args.get("level_dbm", -60.0)))
    return _format_result({"status": "ok", "band": band, "dl_channel": args.get("dl_channel")})


async def _handle_wcdma_sig_cell_on(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.wcdma_sig_set_state(True)
    return _format_result({"status": "ok", "cell": "ON"})


async def _handle_wcdma_sig_cell_off(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.wcdma_sig_set_state(False)
    return _format_result({"status": "ok", "cell": "OFF"})


async def _handle_wcdma_sig_get_state(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    return _format_result(
        {
            "cell_state": (await cmw.wcdma_sig_state_all()).strip(),
            "connection_state": (await cmw.wcdma_sig_connection_state()).strip(),
        }
    )


async def _handle_wcdma_meas_tx(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.wcdma_meas_configure(stat_count=int(args.get("stat_count", 10)))
    await cmw.wcdma_meas_init()
    result = await cmw.wcdma_meas_fetch_power()
    return _format_result(result.to_dict())


async def _handle_wcdma_sig_ber(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.wcdma_sig_fetch_ber()
    return _format_result(result.to_dict())


registry.register(
    Tool(
        name="cmw_wcdma_sig_configure",
        description=(
            "Configure a WCDMA signaling cell (band, DL UARFCN, level). Requires "
            "WCDMA signaling license; app-note-derived - validate on hardware."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "band": {"type": "string", "description": "CMW WCDMA band token (e.g. OB1)"},
                "dl_channel": {"type": "integer", "description": "Downlink UARFCN"},
                "level_dbm": {"type": "number", "default": -60},
                **_HOST_PORT,
            },
        },
    ),
    _handle_wcdma_sig_configure,
)

registry.register(
    Tool(
        name="cmw_wcdma_sig_cell_on",
        description="Turn the WCDMA signaling cell on.",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_wcdma_sig_cell_on,
)

registry.register(
    Tool(
        name="cmw_wcdma_sig_cell_off",
        description="Turn the WCDMA signaling cell off.",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_wcdma_sig_cell_off,
)

registry.register(
    Tool(
        name="cmw_wcdma_sig_get_state",
        description="Read WCDMA cell state and RRC/connection state.",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_wcdma_sig_get_state,
)

registry.register(
    Tool(
        name="cmw_wcdma_meas_tx",
        description="Configure + trigger + fetch WCDMA UE TX power (MEValuation).",
        inputSchema={
            "type": "object",
            "properties": {"stat_count": {"type": "integer", "default": 10}, **_HOST_PORT},
        },
    ),
    _handle_wcdma_meas_tx,
)

registry.register(
    Tool(
        name="cmw_wcdma_sig_ber",
        description="Fetch WCDMA RX BER (reliability + BER%).",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_wcdma_sig_ber,
)

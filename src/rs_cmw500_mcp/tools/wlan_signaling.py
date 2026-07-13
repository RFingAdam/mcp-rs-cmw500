"""WLAN signaling (Access-Point emulation) tools for LTE+Wi-Fi coexistence.

The existing ``wlan`` module measures WLAN in non-signaling mode. This module
emulates an AP so a DUT can associate and pass traffic while an LTE aggressor
runs simultaneously (the CMW500's multi-technology strength).

IMPORTANT: these commands are derived from R&S application notes (1C106/1C107),
not from field-validated scripts, and require the WLAN (advanced) signaling
license. Validate on hardware. Prompts gate these tools on cmw_query_options.
The DUT-side throughput metric (DAU/iPerf) is not wrapped here; reach it via the
raw-SCPI tools + the WLAN signaling SCPI reference resource once licensed.
"""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from .registry import registry
from .shared import _format_result, _get_cmw

logger = logging.getLogger(__name__)

_HOST_PORT = {"host": {"type": "string"}, "port": {"type": "integer"}}


async def _handle_wlan_sig_configure_ap(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.wlan_sig_set_route(args.get("scenario", "SAL"))
    await cmw.wlan_sig_set_standard(args.get("standard", "HEOFdm"))
    await cmw.wlan_sig_set_bandwidth(args.get("bandwidth", "BW20"))
    if args.get("frequency_hz") is not None:
        await cmw.wlan_sig_set_frequency(float(args["frequency_hz"]))
    elif args.get("channel") is not None:
        await cmw.wlan_sig_set_channel(int(args["channel"]))
    await cmw.wlan_sig_set_level(float(args.get("level_dbm", -50.0)))
    await cmw.wlan_sig_set_ssid(args.get("ssid", "CMW_AP"))
    security = args.get("security", "DISabled")
    await cmw.wlan_sig_set_security(security)
    if args.get("passphrase"):
        await cmw.wlan_sig_set_passphrase(args["passphrase"])
    return _format_result(
        {
            "status": "ok",
            "standard": args.get("standard", "HEOFdm"),
            "bandwidth": args.get("bandwidth", "BW20"),
            "ssid": args.get("ssid", "CMW_AP"),
            "security": security,
            "level_dbm": float(args.get("level_dbm", -50.0)),
        }
    )


async def _handle_wlan_sig_ap_on(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.wlan_sig_set_state(True)
    return _format_result({"status": "ok", "ap": "ON"})


async def _handle_wlan_sig_ap_off(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.wlan_sig_set_state(False)
    return _format_result({"status": "ok", "ap": "OFF"})


async def _handle_wlan_sig_get_state(args: dict[str, Any]) -> CallToolResult:
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    ap_state = (await cmw.wlan_sig_state_all()).strip()
    conn_state = (await cmw.wlan_sig_connection_state()).strip()
    return _format_result({"ap_state": ap_state, "connection_state": conn_state})


# =============================================================================
# Registration
# =============================================================================

registry.register(
    Tool(
        name="cmw_wlan_sig_configure_ap",
        description=(
            "Emulate a Wi-Fi AP (standard, bandwidth, channel/frequency, SSID, "
            "security, TX level) for LTE+Wi-Fi coexistence. Requires the WLAN "
            "signaling license (check with cmw_query_options). Derived from R&S "
            "app notes - validate on hardware."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "standard": {
                    "type": "string",
                    "description": "CMW WLAN standard token (e.g. GOFDm, HTOFdm, VHTofdm, HEOFdm)",
                    "default": "HEOFdm",
                },
                "bandwidth": {
                    "type": "string",
                    "enum": ["BW20", "BW40", "BW80", "BW160"],
                    "default": "BW20",
                },
                "channel": {"type": "integer", "description": "Operating channel number"},
                "frequency_hz": {
                    "type": "number",
                    "description": "Center frequency in Hz (overrides channel if set)",
                },
                "ssid": {"type": "string", "default": "CMW_AP"},
                "security": {
                    "type": "string",
                    "description": "Security type token (DISabled/WPA/WPA2/WPA3)",
                    "default": "DISabled",
                },
                "passphrase": {"type": "string", "description": "WPA passphrase (test network)"},
                "level_dbm": {"type": "number", "default": -50},
                "scenario": {"type": "string", "default": "SAL"},
                **_HOST_PORT,
            },
        },
    ),
    _handle_wlan_sig_configure_ap,
)

registry.register(
    Tool(
        name="cmw_wlan_sig_ap_on",
        description="Switch the emulated Wi-Fi AP on (WLAN signaling license required).",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_wlan_sig_ap_on,
)

registry.register(
    Tool(
        name="cmw_wlan_sig_ap_off",
        description="Switch the emulated Wi-Fi AP off.",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_wlan_sig_ap_off,
)

registry.register(
    Tool(
        name="cmw_wlan_sig_get_state",
        description="Read the emulated AP state and DUT association/connection state.",
        inputSchema={"type": "object", "properties": {**_HOST_PORT}},
    ),
    _handle_wlan_sig_get_state,
)

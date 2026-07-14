"""MCP resources: a curated SCPI reference + dynamic capability discovery.

These resources let an LLM construct correct SCPI for any licensed subsystem via
the raw-SCPI tools, and adapt to the installed options. Content is curated and
short (no reproduction of the full R&S manual); the band-plan and capabilities
resources are generated dynamically from live data.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.types import Resource
from pydantic import AnyUrl

from ..models import band_plans

logger = logging.getLogger(__name__)

MIME_MD = "text/markdown"
MIME_JSON = "application/json"

_SCPI_INDEX = """# CMW500 SCPI quick reference (index)

Universal patterns used across subsystems:
- `*IDN?` identity, `*OPT?` / `SYSTem:BASE:OPTion:LIST?` installed options.
- `*RST` reset, `SYSTem:PRESet` preset, `*CLS` clear status, `*OPC?` operation complete.
- `SYSTem:ERRor?` drains the error queue (0,"No error" when clean).
- Config with `CONFigure:<tech>:...`; start with `INITiate:...`; read with
  `FETCh:...`/`READ:...`. Signaling cell/AP state via `SOURce:<tech>:SIGN:...:STATe`.
- First field of most `FETCh`/`READ` results is a **reliability** code
  (see cmw://reference/reliability-codes).

Per-subsystem sheets: cmw://scpi/lte-signaling, cmw://scpi/bluetooth-signaling,
cmw://scpi/wlan-signaling, cmw://scpi/gprf, cmw://scpi/routing, cmw://scpi/system.
Data: cmw://reference/band-plan, cmw://reference/reliability-codes,
cmw://reference/band-presets. Live: cmw://capabilities.

For anything not wrapped by a typed tool, use cmw_scpi_send / cmw_scpi_query
(enable with CMW_ALLOW_RAW_SCPI=true) and check cmw_system_error afterwards.
"""

_SCPI_LTE = """# LTE signaling + receiver sensitivity (Extended BLER)

Cell / attach lifecycle (RX flow uses the SOURce form):
- `SOURce:LTE:SIGN1:CELL:STAT ON|OFF`         cell on/off
- `SOURce:LTE:SIGN1:CELL:STAT:ALL?`           -> e.g. `ON,ADJ` when stable
- `FETCh:LTE:SIGN1:PSW:STAT?`                  -> `ATT` when the UE is attached
- `CONFigure:LTE:SIGN1:BAND OB<n>`             operating band (OB7 = band 7)
- `CONFigure:LTE:SIGN1:CELL:BANDwidth:PCC:DL B050`   5 MHz (B014/B030/B050/B100/B150/B200)
- `CONFigure:LTE:SIGN1:RFSettings:PCC:CHANnel:DL <earfcn>`  (and :UL)

Extended BLER (receiver sensitivity):
- `CONFigure:LTE:SIGN1:DL:PCC:RSEP:LEV <dBm/15kHz>`   DL RS-EPRE level
- `CONFigure:LTE:SIGN1:EBL:REP SING`                  single-shot
- `CONFigure:LTE:SIGN1:EBL:SFR 100|500`               measured subframes
- `INITiate:LTE:SIGN1:EBL`                            start
- `FETCh:INT:LTE:SIGN1:EBL:PCC:REL?`                  -> reliability,...,...,BLER%,...
  (reliability 19 = call dropped / not attached)

Typed tools: cmw_lte_rx_configure, cmw_lte_attach_wait, cmw_lte_rx_measure_bler,
cmw_lte_rx_sensitivity (plus TX measurement tools cmw_lte_meas_*).
"""

_SCPI_BT = """# Bluetooth / BLE signaling (receiver PER)

CMW as Central, connection established, then:
- `*CLS`
- `CONFigure:BLUetooth:SIGN1:RXQ:PACK:NMOD:LEN:LE1M <packets>`
- `CONFigure:BLUetooth:SIGN1:RFS:NMOD:MCH:LEN <channel>`   data channel 0..39
- `CONFigure:BLUetooth:SIGN1:RFS:LEV <dBm>`                CMW TX level to DUT
- `READ:BLUetooth:SIGN1:RXQ:PER:NMOD:LEN:LE1M?`            -> reliability,PER%,...
  (reliability 0 = valid)
- `CALL:BLUetooth:SIGN1:CONN:ACT:LES CONN|DET`             connect / detach

BLE data-channel frequency = 2402 + 2*channel MHz; advertising channels {0,12,39}.
Typed tools: cmw_ble_sig_configure, cmw_ble_sig_connect/detach,
cmw_ble_sig_measure_per, cmw_ble_sig_sensitivity.
"""

_SCPI_WLAN = """# WLAN signaling (AP emulation) - requires WLAN signaling license

Derived from R&S app notes (1C106/1C107); validate on hardware. `WLAN:SIGN1`:
- `ROUTe:WLAN:SIGN1:SCENario <scenario>`
- `CONFigure:WLAN:SIGN1:STANdard <GOFDm|HTOFdm|VHTofdm|HEOFdm|...>`
- `CONFigure:WLAN:SIGN1:RFSettings:BWIDth BW20|BW40|BW80|BW160`
- `CONFigure:WLAN:SIGN1:RFSettings:CHANnel <ch>` or `:FREQuency <Hz>`
- `CONFigure:WLAN:SIGN1:RFSettings:LEVel <dBm>`
- `CONFigure:WLAN:SIGN1:CONNection:SSID '<ssid>'`
- `SOURce:WLAN:SIGN1:STATe ON|OFF`, `SOURce:WLAN:SIGN1:STATe:ALL?`
- `SENSe:WLAN:SIGN1:CONNection:STATe?`

DUT throughput (DAU/iPerf) is license-gated and not wrapped as a tool; drive it
via raw SCPI once the option is present. Typed tools: cmw_wlan_sig_configure_ap,
cmw_wlan_sig_ap_on/off, cmw_wlan_sig_get_state.
"""

_SCPI_GPRF = """# GPRF generator / analyzer (general-purpose RF)

Generator (aggressor/CW/ARB source, e.g. sub-GHz coex interferer):
- `SOURce:GPRF:GENerator1:RFSettings:FREQuency <Hz>` / `:LEVel <dBm>`
- `SOURce:GPRF:GENerator1:BBMode CW|ARB`, `SOURce:GPRF:GENerator1:STATe ON|OFF`
- ARB: `SOURce:GPRF:GENerator1:ARB:FILE '<path>'`, `:ARB:REPetition CONTinuous|SINGle`

Analyzer:
- `CONFigure:GPRF:MEASurement1:RFSettings:FREQuency <Hz>` / `:ENPower <dBm>`
- `CONFigure:GPRF:MEASurement1:POWer:SCOunt|MLENgth|REPetition ...`
- `INITiate:GPRF:MEASurement1:POWer`, `FETCh:GPRF:MEASurement1:POWer:CURRent?`

Typed tools: cmw_gen_*, cmw_meas_*.
"""

_SCPI_ROUTING = """# RF routing / signal path (coex needs distinct connectors)

- GPRF: `ROUTe:GPRF:GENerator1:SCENario:SPATh <connector>`,
  `ROUTe:GPRF:MEASurement1:SCENario:SPATh <connector>`
- Non-signaling meas: `ROUTe:WLAN:MEAS<n>:SCENario ...`, `ROUTe:BLUetooth:MEAS<n>:SCENario ...`

For simultaneous multi-tech (coex) operation, assign each technology a **separate**
RF connector/converter. The server cannot enforce cabling; use
cmw_coex_validate_routing to catch a shared-connector mistake before a sweep.
Physical note: strong same-band aggressors (e.g. LTE B7 near a 2.4 GHz BLE
receiver) may need a bandpass filter on the victim path in addition to separate
connectors.
"""

_SCPI_SYSTEM = """# System / common commands

- `*IDN?`, `*RST`, `SYSTem:PRESet`, `*CLS`, `*OPC?`
- `SYSTem:BASE:OPTion:LIST?` installed options (see cmw://capabilities)
- `SYSTem:ERRor?` drain error queue
- `SYSTem:GENerator:ALL:OFF`, `SYSTem:MEASurement:ALL:OFF` safe state

Typed tools: cmw_identify, cmw_query_options, cmw_reset, cmw_preset,
cmw_system_all_off, cmw_system_error, cmw_scpi_send/query, cmw_scpi_query_opc.
"""

_RELIABILITY = """# CMW500 reliability indicators (result field 0)

| Code | Meaning |
|------|---------|
| 0  | OK - measurement valid |
| 1  | Measurement timeout |
| 2  | Capture buffer overflow |
| 3  | Overdriven / underdriven input |
| 7  | Not attempted / measurement off |
| 15 | Missing option / license |
| 19 | Call dropped / UE not attached (LTE EBL) |
| 26 | No connection / signal lost |

Non-zero reliability means the numeric results should not be trusted. The exact
set depends on the application and firmware; consult the R&S manual for the full
table. In this server: LTE EBL 19 -> dropped; BLE PER 0 -> valid.
"""

# Static markdown resources keyed by URI: uri -> (name, description, content).
_STATIC: dict[str, tuple[str, str, str]] = {
    "cmw://scpi/index": (
        "CMW500 SCPI index",
        "SCPI quick-reference index and universal patterns",
        _SCPI_INDEX,
    ),
    "cmw://scpi/lte-signaling": (
        "LTE signaling SCPI",
        "LTE cell/attach + Extended-BLER receiver SCPI",
        _SCPI_LTE,
    ),
    "cmw://scpi/bluetooth-signaling": (
        "BLE signaling SCPI",
        "BLE signaling PER receiver SCPI",
        _SCPI_BT,
    ),
    "cmw://scpi/wlan-signaling": (
        "WLAN signaling SCPI",
        "WLAN AP-emulation SCPI (license-gated)",
        _SCPI_WLAN,
    ),
    "cmw://scpi/gprf": ("GPRF SCPI", "GPRF generator/analyzer SCPI", _SCPI_GPRF),
    "cmw://scpi/routing": (
        "Routing SCPI",
        "RF routing / signal-path notes for coex",
        _SCPI_ROUTING,
    ),
    "cmw://scpi/system": ("System SCPI", "System/common SCPI commands", _SCPI_SYSTEM),
    "cmw://reference/reliability-codes": (
        "Reliability codes",
        "CMW result reliability indicator table",
        _RELIABILITY,
    ),
}

# Dynamic resources keyed by URI: uri -> (name, description, mime).
_DYNAMIC: dict[str, tuple[str, str, str]] = {
    "cmw://reference/band-plan": (
        "Band plan (JSON)",
        "EARFCN tables, band edges, BLE channel math",
        MIME_JSON,
    ),
    "cmw://reference/band-presets": (
        "Band presets (JSON)",
        "Neutral, overridable LTE band-selection presets",
        MIME_JSON,
    ),
    "cmw://capabilities": (
        "Live capabilities (JSON)",
        "Installed options queried from the instrument",
        MIME_JSON,
    ),
}


def list_resources() -> list[Resource]:
    resources = [
        Resource(uri=AnyUrl(uri), name=name, description=desc, mimeType=MIME_MD)
        for uri, (name, desc, _content) in _STATIC.items()
    ]
    resources += [
        Resource(uri=AnyUrl(uri), name=name, description=desc, mimeType=mime)
        for uri, (name, desc, mime) in _DYNAMIC.items()
    ]
    return resources


def _band_plan_json() -> str:
    data = {
        "lte_fdd_bands": {
            str(b): {
                "dl_low_mhz": v[0],
                "n_offs_dl": v[1],
                "ul_low_mhz": v[2],
                "n_offs_ul": v[3],
                "earfcn_min": v[4],
                "earfcn_max": v[5],
            }
            for b, v in band_plans.LTE_FDD_BANDS.items()
        },
        "band_edges_mhz": {
            k: {
                "display": e.display,
                "ul_start": e.ul_start,
                "ul_end": e.ul_end,
                "dl_start": e.dl_start,
                "dl_end": e.dl_end,
                "is_lte": e.is_lte,
            }
            for k, e in band_plans.BAND_EDGES.items()
        },
        "ble": {
            "channel_freq_mhz": "2402 + 2*channel",
            "advertising_channels": sorted(band_plans.BLE_ADV_CHANNELS),
        },
    }
    return json.dumps(data, indent=2)


def _band_presets_json() -> str:
    from ..config import get_settings

    settings = get_settings()
    path = (
        Path(settings.band_presets_file)
        if settings.band_presets_file
        else Path(__file__).parent / "band_presets.json"
    )
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        return json.dumps({"error": f"Could not read presets file {path}: {exc}"})


async def _capabilities_json() -> str:
    # Import here to avoid a resources<->tools import cycle at module load.
    from ..tools.shared import _get_cmw

    try:
        cmw = await _get_cmw()
        options = await cmw.query_options()
        info = cmw.info.to_dict() if cmw.info else {}
        return json.dumps({"online": True, "instrument": info, "options": options}, indent=2)
    except Exception as exc:  # noqa: BLE001 - offline is a normal, reportable state
        return json.dumps(
            {
                "online": False,
                "note": "Instrument not reachable; connect to query live options.",
                "detail": str(exc),
            },
            indent=2,
        )


async def read_resource(uri: str) -> tuple[str, str]:
    """Return (content, mime_type) for a cmw:// resource URI."""
    uri = str(uri)
    if uri in _STATIC:
        return _STATIC[uri][2], MIME_MD
    if uri == "cmw://reference/band-plan":
        return _band_plan_json(), MIME_JSON
    if uri == "cmw://reference/band-presets":
        return _band_presets_json(), MIME_JSON
    if uri == "cmw://capabilities":
        return await _capabilities_json(), MIME_JSON
    raise ValueError(f"Unknown resource: {uri}")

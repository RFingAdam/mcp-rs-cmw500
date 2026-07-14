"""MCP prompts: guided coexistence / RX workflows.

Each prompt returns a user message describing the exact tool-call sequence, with
neutral defaults, safety reminders, and links to the cmw:// SCPI reference
resources. Prompts are guidance layered on top of the typed tools - they do not
replace them.
"""

from __future__ import annotations

from typing import Any

from mcp.types import GetPromptResult, Prompt, PromptArgument, PromptMessage, TextContent


def _arg(name: str, description: str, required: bool = False) -> PromptArgument:
    return PromptArgument(name=name, description=description, required=required)


_SAFETY = (
    "Safety & correctness reminders:\n"
    "- Respect RF power limits (the driver clamps generator/DL levels).\n"
    "- Turn the cell/AP OFF between major reconfigurations.\n"
    "- After raw SCPI, call `cmw_system_error` to confirm the queue is clean.\n"
    "- For simultaneous multi-tech coex, each technology needs a SEPARATE RF "
    "connector; validate with `cmw_coex_validate_routing`. Strong same-band "
    "aggressors may also need a bandpass filter on the victim path (hardware).\n"
    "- Call `cmw_query_options` first and adapt to the installed licenses."
)


def _lte_ble_desense(a: dict[str, Any]) -> str:
    bands = a.get("lte_bands", "e.g. 7, 20")
    return f"""Goal: measure LTE -> BLE receiver desense by sweeping an LTE aggressor while
measuring BLE PER sensitivity across data channels.

Bench: LTE and BLE on separate RF connectors (e.g. RF1COM / RF2COM); CMW BLE
signaling running as Central with an established connection to the DUT.

Suggested tool sequence:
1. `cmw_connect` (host optional) then `cmw_query_options` (confirm LTE signaling + BLE signaling).
2. `cmw_coex_validate_routing` with your connector map, e.g. {{"lte":"RF1COM","ble":"RF2COM"}}.
3. `cmw_ble_sig_configure` (packets, default 100) and `cmw_ble_sig_connect`.
4. `cmw_coex_plan` with lte_bands=[{bands}], earfcn_spacing (default 25),
   include_baseline=true (adds an aggressor-off baseline row), and BLE channel
   range/steps. Note the returned sweep_id and total_points.
5. Loop `cmw_coex_step` (sweep_id, max_points) until status == "complete",
   reporting progress each step.
6. `cmw_coex_result` for the full matrix (rows = LTE condition, cols = BLE channel,
   cell = BLE sensitivity dBm) plus long-format rows.

Optionally run `cmw_imd_analyze`/`cmw_imd_batch` first to pick the most likely
problem bands/channels. See cmw://scpi/lte-signaling and cmw://scpi/bluetooth-signaling.

{_SAFETY}"""


def _lte_wifi_coex(a: dict[str, Any]) -> str:
    return f"""Goal: exercise native LTE + Wi-Fi coexistence - emulate an LTE eNB and a Wi-Fi
AP simultaneously and observe the Wi-Fi link under the LTE aggressor.

Requires the WLAN signaling license (check `cmw_query_options`). If absent, fall
back to using the GPRF generator as the aggressor instead of a live LTE cell.

Suggested tool sequence:
1. `cmw_connect`, `cmw_query_options`.
2. `cmw_coex_validate_routing` {{"lte":"RF1COM","wlan":"RF2COM"}} - separate connectors.
3. Wi-Fi AP: `cmw_wlan_sig_configure_ap` (standard {a.get("wlan_standard", "HEOFdm")},
   bandwidth {a.get("wlan_bw", "BW20")}, channel/frequency, SSID, level) then
   `cmw_wlan_sig_ap_on`; associate the DUT and confirm with `cmw_wlan_sig_get_state`.
4. LTE aggressor: `cmw_lte_rx_configure` (band {a.get("lte_band", "7")}) + `cmw_lte_attach_wait`,
   or set an uplink/downlink condition as your aggressor.
5. Measure the Wi-Fi victim metric (throughput via DAU is license-gated and
   reached through raw SCPI + cmw://scpi/wlan-signaling; TX quality via cmw_wlan_* ).
6. Repeat across LTE conditions and compare against an LTE-off baseline.

{_SAFETY}"""


def _rx_sensitivity(a: dict[str, Any]) -> str:
    tech = a.get("technology", "LTE-BLER or BLE-PER")
    return f"""Goal: find single-technology receiver sensitivity ({tech}).

LTE (BLER): `cmw_lte_rx_configure` (band, bandwidth) -> `cmw_lte_attach_wait` ->
`cmw_lte_rx_sensitivity` per EARFCN (coarse+fine search to the target BLER,
default 10%). Sensitivity is the lowest DL RS-EPRE level meeting the target.

BLE (PER): ensure the BLE signaling link is up -> `cmw_ble_sig_configure` ->
`cmw_ble_sig_sensitivity` per channel (coarse+fine search to the target PER).

Use `cmw_lte_rx_measure_bler` / `cmw_ble_sig_measure_per` for single points while
debugging. See cmw://reference/reliability-codes for interpreting results.

{_SAFETY}"""


def _imd_analysis(a: dict[str, Any]) -> str:
    return f"""Goal: predict coexistence interference before touching hardware.

Use `cmw_imd_analyze` for one/two named carriers into a victim band
(victim {a.get("victim", "e.g. GNSS_L1")}), or `cmw_imd_batch` to scan many
aggressors into a victim with physical-radio constraint rules. Both report
harmonic and intermodulation products that fall into the victim receive band,
with order, equation, and frequency span.

Then feed the flagged aggressor bands/frequencies into a live coex sweep
(`cmw_coex_plan`) or an aggressor sweep. Band keys and edges are in
cmw://reference/band-plan. No instrument connection is needed for this analysis."""


def _subghz_aggressor(a: dict[str, Any]) -> str:
    return f"""Goal: sub-GHz aggressor sweep (e.g. LTE low-band or ISM near an 802.11ah/HaLow
link). The CMW500 cannot generate/measure HaLow natively, so use the GPRF
generator as the aggressor and measure the HaLow victim externally.

Suggested sequence:
1. `cmw_imd_analyze` (carrier1 e.g. HALOW_US, victim = the DUT's RX band) to
   choose aggressor frequencies/levels worth testing.
2. `cmw_set_port` to route the GPRF generator to the aggressor connector.
3. For each aggressor point: `cmw_gen_set_frequency` + `cmw_gen_set_level` +
   `cmw_gen_output_on`; hold while the HaLow link PER/throughput is recorded
   externally (companion radio or DUT stats); then `cmw_gen_output_off`.
4. Compare victim performance with the aggressor on vs off.

This documents the sub-GHz coex path; the victim measurement is off-instrument.

{_SAFETY}"""


_BUILDERS = {
    "lte_ble_desense_sweep": _lte_ble_desense,
    "lte_wifi_coexistence_throughput": _lte_wifi_coex,
    "rx_sensitivity_search": _rx_sensitivity,
    "imd_hit_analysis": _imd_analysis,
    "subghz_aggressor_sweep": _subghz_aggressor,
}

_PROMPTS = [
    Prompt(
        name="lte_ble_desense_sweep",
        description="Guide an LTE->BLE receiver-desense coexistence sweep (aggressor x victim).",
        arguments=[
            _arg("lte_bands", "LTE aggressor bands, e.g. '7, 20'"),
            _arg("ble_channel_range", "BLE data channel range, e.g. '1-38'"),
            _arg("host", "CMW500 host (optional; defaults to config)"),
        ],
    ),
    Prompt(
        name="lte_wifi_coexistence_throughput",
        description="Guide native LTE + Wi-Fi coexistence (emulate eNB + AP simultaneously).",
        arguments=[
            _arg("lte_band", "LTE aggressor band"),
            _arg("wlan_standard", "Wi-Fi standard token (e.g. HEOFdm)"),
            _arg("wlan_bw", "Wi-Fi bandwidth (BW20/BW40/BW80/BW160)"),
        ],
    ),
    Prompt(
        name="rx_sensitivity_search",
        description="Guide a single-technology receiver sensitivity search (LTE-BLER or BLE-PER).",
        arguments=[_arg("technology", "'LTE-BLER' or 'BLE-PER'")],
    ),
    Prompt(
        name="imd_hit_analysis",
        description="Guide pure-computation intermod/harmonic coexistence analysis (no hardware).",
        arguments=[_arg("victim", "Victim band key, e.g. GNSS_L1")],
    ),
    Prompt(
        name="subghz_aggressor_sweep",
        description="Guide a sub-GHz GPRF-aggressor sweep (e.g. LTE/ISM near a HaLow victim link).",
        arguments=[_arg("victim", "Victim RX band the DUT uses")],
    ),
]


def list_prompts() -> list[Prompt]:
    return list(_PROMPTS)


def get_prompt(name: str, arguments: dict[str, Any] | None = None) -> GetPromptResult:
    builder = _BUILDERS.get(name)
    if builder is None:
        raise ValueError(f"Unknown prompt: {name}")
    text = builder(arguments or {})
    prompt = next(p for p in _PROMPTS if p.name == name)
    return GetPromptResult(
        description=prompt.description,
        messages=[PromptMessage(role="user", content=TextContent(type="text", text=text))],
    )

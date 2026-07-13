# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] — 2026-07-13

### Added

- **Per-unit bench profile** (`profile.py`, `tools/profile_tools.py`) — one JSON
  per unit capturing connection, safety limits, RF routing map, external
  attenuation, and expected licenses. Auto-loaded via `CMW_PROFILE_FILE`; tools
  consult it for defaults only when an arg is omitted (explicit wins). Tools
  `cmw_profile_load/show/save/list/apply` + `cmw://profile` resource.
  `cmw_profile_apply` pushes only well-grounded GPRF routing/attenuation;
  signaling routing is returned as intent.
- **Test-plan + reporting engine** (`testplan/`, `tools/testplan_tools.py`) —
  ordered steps that invoke any registered tool (domain-agnostic via the
  registry), with pass/fail limits on dotted result paths, `${ctx.key}` chaining,
  setup/main/teardown roles, and abort-on-fail (teardown still runs). Resumable
  run + Markdown / self-contained HTML / CSV reports (no new deps). Tools
  `cmw_testplan_define/step/run/result/report/save/load/list`.
- **New first-class domains**: GSM/GPRS signaling (`tools/gsm_signaling.py`),
  WCDMA/UMTS signaling (`tools/wcdma_signaling.py`), and WLAN throughput / DAU
  (`tools/wlan_throughput.py`: IP throughput, iPerf, ping) — the Wi-Fi victim
  metric for LTE+Wi-Fi coex. New `ThroughputResult`. GSM/WCDMA and iPerf/ping
  are app-note-derived; the DAU THRoughput commands are well-grounded.
- **Bench validation** (`licensing.py`, `tools/selftest.py`) — `cmw_selftest`
  identifies the unit, lists options, and runs a read-only smoke per licensed
  domain; `bench_bringup` prompt; hardware integration tests gated by
  `CMW_TEST_HOST`.
- SCPI reference resources for GSM/WCDMA/WLAN-throughput.

### Changed

- Tool count **102 → 131**; tests **457 → ~510**. New config: `CMW_PROFILE_FILE`,
  `CMW_PROFILE_DIR`, `CMW_TESTPLAN_DIR`, `CMW_REPORT_DIR`.
- Cleared all pre-existing `mypy --strict` errors (annotations across templates,
  state, limits, scpi_socket/driver context managers; scoped override for the
  untyped MCP-SDK decorators in `server.py`).
- Version bumped to 0.5.0.

## [0.4.0] — 2026-07-13

### Added

- **LTE receiver sensitivity (Extended BLER)** — cell attach lifecycle, single
  EBL measurements, and a coarse+fine sensitivity search
  (`cmw_lte_rx_configure`, `cmw_lte_attach_wait`, `cmw_lte_rx_measure_bler`,
  `cmw_lte_rx_sensitivity`).
- **BLE signaling PER** — a signaling domain distinct from the existing
  non-signaling measurement block: connect/detach, single PER reads, and a
  PER sensitivity search (`cmw_ble_sig_*`).
- **WLAN signaling (AP emulation)** — for native LTE+Wi-Fi coexistence
  (`cmw_wlan_sig_configure_ap`, `cmw_wlan_sig_ap_on/off`,
  `cmw_wlan_sig_get_state`). License-gated; SCPI derived from R&S app notes and
  flagged for bench validation.
- **Coexistence orchestration** — a resumable LTE(aggressor)↔BLE(victim) desense
  sweep with a rows×columns sensitivity matrix, plus a routing-collision guard
  (`cmw_coex_plan/step/result/measure_point`, `cmw_coex_validate_routing`).
- **IMD / coexistence planner** — pure-computation harmonic + intermodulation
  analysis into a victim band with physical-radio constraint rules
  (`cmw_imd_analyze`, `cmw_imd_batch`), backed by a standard band-plan module
  (EARFCN tables, band edges incl. GNSS/Wi-Fi/HaLow, BLE channel math).
- **System / SCPI-hygiene tools** — `cmw_system_error` (drain `SYSTem:ERRor?`)
  and `cmw_scpi_query_opc` (OPC-synced raw command); optional
  `CMW_AUTO_ERROR_CHECK`.
- **MCP resources** — a curated per-subsystem SCPI reference, a reliability-code
  table, a JSON band-plan dump, overridable band presets, and dynamic
  `cmw://capabilities` (live installed options).
- **MCP prompts** — guided coex/RX workflows: `lte_ble_desense_sweep`,
  `lte_wifi_coexistence_throughput`, `rx_sensitivity_search`,
  `imd_hit_analysis`, `subghz_aggressor_sweep`.
- Shared, hardware-agnostic coarse+fine threshold-search primitive
  (`driver/search.py`) reused by LTE-BLER and BLE-PER.
- A `MockSCPISocket` test double for hardware-free SCPI-string / parser tests.
- CI scrub-check guarding against customer/project identifiers.

### Changed

- Tool count increased from **79 to 101**; test count from 373 to **453**.
- Raw SCPI now **disabled by default** (`allow_raw_scpi=False`) — the shipped
  code default now matches the documented secure posture.
- Corrected a UL-frequency mapping bug carried in from the source scripts
  (paired UL now uses the DL channel offset per 3GPP TS 36.101).
- `validate_safe_path` now explicitly rejects null bytes (cross-platform).
- Fixed the version-string mismatch, the hard-coded developer path in
  `.mcp.json`, and the inaccurate direct-driver example in the README.
- Version bumped to 0.4.0.

## [0.3.0] — 2026-05-13

### Changed
- **License: Apache-2.0 → AGPL-3.0-or-later.** Aligns with the
  eng-mcp-suite toolkit-wide AGPL move. R&S hardware and proprietary
  client software are independent of this wrapper.

## [0.2.0] - 2025-02-21

### Added

- **WLAN non-signaling support** -- 11 new MCP tools for 802.11a/b/g/n/ac/ax testing
  - TX power, EVM, spectrum flatness, and frequency error measurements
  - Configurable standard, bandwidth (20/40/80/160 MHz), frequency, and expected power
  - Multi-instance measurement support (MEAS1-MEASn)
- **Bluetooth/BLE non-signaling support** -- 11 new MCP tools
  - Classic Bluetooth: DH1/DH3/DH5/DM1/DM3/DM5 packet types
  - BLE: 1M, 2M, Coded S2, Coded S8 PHY modes
  - TX power, modulation (DEVM), and frequency offset/drift measurements
- **Advanced GPRF tools** -- 6 new tools for trigger configuration, power filters, baseband mode, RF port selection, user margin, and system-wide off
- **Measurement templates** -- 4 new pre-built configs
  - `ble_tx` -- BLE TX measurement (1M/2M/Coded S2 presets)
  - `ble_rx` -- BLE RX sensitivity via GPRF generator
  - `bt_classic_tx` -- Bluetooth Classic TX (DH1/DH5 presets)
  - `wlan_rx` -- WLAN RX sensitivity via GPRF generator (Wi-Fi 6 presets)
- **Tool registry architecture** -- modular tool system replacing monolithic dispatch
  - Each technology in its own module with auto-registration
  - Centralized error handling with proper `isError` propagation
- **CI/CD pipeline** -- GitHub Actions with Python 3.10/3.11/3.12 matrix
  - Lint (ruff check), format (ruff format), test (pytest + coverage), typecheck (mypy)
- **Data models** -- typed enums, config dataclasses, and result dataclasses for WLAN and Bluetooth
- **SCPI input sanitization** -- protection against injection attacks
- **Raw SCPI guard** -- `CMW_ALLOW_RAW_SCPI` setting (default: disabled)
- **Asyncio locks** -- connection pool, template, and measurement locks for concurrent safety
- **Integration test marker** -- `@pytest.mark.integration` for hardware-dependent tests

### Changed

- Tool count increased from 51 to **79 tools**
- Test count increased from 248 to **373 tests**
- Source code grew from ~3,500 to **7,087 lines**
- `lte_meas_configure()` -- de-stubbed with real SCPI (stat count, repetition)
- `lte_configure_bearer()` -- de-stubbed with real SCPI (APN, IP version)
- `meas_configure_spectrum()` -- de-stubbed with real SCPI (center freq, span, RBW, detector)
- `wlan_tx` template -- now uses native WLAN SCPI subsystem instead of GPRF workaround
- Version bumped to 0.2.0

### Architecture

- Decomposed `tools.py` (1,621 lines) into `tools/` package (10 modules)
- Added `tools/registry.py` with `ToolRegistry` singleton pattern
- Added `tools/shared.py` with connection pooling, locks, and shared helpers
- Each technology module (connection, gprf, lte, wlan, bluetooth, scpi) self-registers tools at import time

## [0.1.0] - 2025-01-15

### Added

- Initial release
- GPRF generator control (frequency, level, ARB waveforms)
- GPRF analyzer measurements (power, spectrum)
- LTE signaling mode (cell configuration, connection management)
- LTE TX measurements (power, EVM, ACLR, SEM)
- Safety limits system
- State save/restore
- Pass/fail limit checking
- 3 measurement templates (LTE TX, GPRF power, non-signaling RX)

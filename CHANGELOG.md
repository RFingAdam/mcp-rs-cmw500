# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

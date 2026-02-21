# R&S CMW500 MCP Server

[![CI](https://github.com/RFingAdam/mcp-rs-cmw500/actions/workflows/ci.yml/badge.svg)](https://github.com/RFingAdam/mcp-rs-cmw500/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-purple.svg)](https://modelcontextprotocol.io)

An open-source [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for automating the **Rohde & Schwarz CMW500** Wideband Radio Communication Tester via direct TCP/IP SCPI (port 5025). No CMWrun dependency required.

> Control your CMW500 from Claude Desktop, VS Code Copilot, or any MCP-compatible AI client -- configure measurements, trigger acquisitions, and fetch results across LTE, WLAN, and Bluetooth with natural language.

## Features

- **79 MCP tools** across 5 RF technology domains
- **LTE signaling** -- cell configuration, NAS/bearer setup, C-DRX, full TX measurements (power, EVM, ACLR, SEM, frequency error)
- **WLAN non-signaling** -- 802.11a/b/g/n/ac/ax, 20/40/80/160 MHz, TX power/EVM/spectrum flatness/frequency error
- **Bluetooth/BLE non-signaling** -- Classic (DH1-DH5) and LE (1M/2M/Coded S2/S8), TX power/modulation/frequency
- **GPRF generator/analyzer** -- CW/ARB output, power/spectrum measurements, configurable triggers and filters
- **Safety system** -- configurable RF power limits, frequency bounds, SCPI input sanitization
- **Measurement templates** -- pre-built configs for common test scenarios (LTE TX, WLAN TX/RX, BLE TX/RX, BT Classic TX)
- **State management** -- save/restore full instrument configuration
- **Pass/fail limits** -- define and check measurement results against specs
- **Asyncio-native** -- concurrent-safe with connection pooling and lock ordering

## Architecture

```
src/rs_cmw500_mcp/
├── server.py              # MCP server (stdio transport)
├── config.py              # Settings via environment / .env
├── exceptions.py          # Exception hierarchy
├── driver/
│   ├── cmw500_driver.py   # SCPI command layer (GPRF, LTE, WLAN, BT)
│   └── scpi_socket.py     # TCP/IP socket transport
├── models/
│   └── cmw_types.py       # Enums, configs, result dataclasses
├── tools/                 # MCP tool registry (79 tools)
│   ├── registry.py        # Tool registration & dispatch
│   ├── shared.py          # Connection pool, locks, helpers
│   ├── connection.py      # Connect/disconnect/discover/identify
│   ├── gprf.py            # Generator & analyzer tools
│   ├── gprf_advanced.py   # Triggers, filters, ports, system control
│   ├── lte.py             # LTE signaling & measurements
│   ├── wlan.py            # WLAN non-signaling measurements
│   ├── bluetooth.py       # Bluetooth/BLE non-signaling measurements
│   ├── scpi.py            # Raw SCPI send/query
│   ├── templates_tools.py # Template list/load/apply
│   ├── limits_tools.py    # Pass/fail limit management
│   └── state_tools.py     # State save/load
├── templates/             # Pre-built measurement configs
│   ├── base.py            # Template base class & serialization
│   ├── lte_tx.py          # LTE TX power measurement
│   ├── gprf_power.py      # GPRF power measurement
│   ├── nonsig_rx.py       # Non-signaling RX sensitivity
│   ├── wlan_tx.py         # WLAN TX measurement
│   ├── wlan_rx.py         # WLAN RX sensitivity
│   ├── ble_tx.py          # BLE TX measurement
│   ├── ble_rx.py          # BLE RX sensitivity
│   └── bt_classic_tx.py   # Bluetooth Classic TX measurement
├── safety/
│   └── validators.py      # RF limit enforcement & SCPI sanitization
├── limits.py              # Pass/fail limit engine
└── state.py               # State serialization
```

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- CMW500 with TCP/IP SCPI enabled on port 5025

### Install

```bash
git clone https://github.com/RFingAdam/mcp-rs-cmw500.git
cd mcp-rs-cmw500
uv pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
# Edit .env with your CMW500 IP address and safety limits
```

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `CMW_DEFAULT_HOST` | `127.0.0.1` | CMW500 IP address |
| `CMW_DEFAULT_PORT` | `5025` | SCPI TCP port |
| `CMW_MAX_GENERATOR_POWER_DBM` | `0` | Max generator output (dBm) |
| `CMW_MAX_EXPECTED_POWER_DBM` | `33` | Max analyzer input (dBm) |
| `CMW_MAX_FREQUENCY_HZ` | `6000000000` | Max frequency (Hz) |
| `CMW_ALLOW_RAW_SCPI` | `false` | Enable raw SCPI commands |

### Run

```bash
# Standalone
rs-cmw500-mcp

# With Claude Desktop - add to your MCP config:
{
  "mcpServers": {
    "rs-cmw500": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcp-rs-cmw500", "run", "rs-cmw500-mcp"]
    }
  }
}
```

## Tool Reference

### Connection (6 tools)

| Tool | Description |
|------|-------------|
| `cmw_discover` | Scan for CMW500 instruments on the network |
| `cmw_connect` | Connect to CMW500 at host:port |
| `cmw_disconnect` | Disconnect from CMW500 |
| `cmw_identify` | Get instrument ID (*IDN?) |
| `cmw_get_status` | Get connection and configuration status |
| `cmw_query_options` | Query installed hardware/software options |

### GPRF Generator (7 tools)

| Tool | Description |
|------|-------------|
| `cmw_gen_set_frequency` | Set output frequency (Hz) |
| `cmw_gen_set_level` | Set output level (dBm) |
| `cmw_gen_output_on` | Enable RF output |
| `cmw_gen_output_off` | Disable RF output |
| `cmw_gen_load_arb` | Load ARB waveform file |
| `cmw_gen_configure_arb` | Configure ARB playback mode |
| `cmw_gen_set_baseband_mode` | Set baseband mode (CW/ARB) |

### GPRF Analyzer (10 tools)

| Tool | Description |
|------|-------------|
| `cmw_meas_set_frequency` | Set measurement frequency (Hz) |
| `cmw_meas_set_expected_power` | Set expected input power (dBm) |
| `cmw_meas_configure_power` | Configure power measurement |
| `cmw_meas_configure_spectrum` | Configure spectrum measurement |
| `cmw_meas_trigger` | Trigger power measurement |
| `cmw_meas_fetch_power` | Fetch power results |
| `cmw_meas_fetch_spectrum` | Fetch spectrum results |
| `cmw_meas_set_trigger` | Set trigger source and threshold |
| `cmw_meas_set_power_filter` | Set measurement filter |
| `cmw_meas_set_user_margin` | Set user margin (dB) |

### GPRF Signal Path (4 tools)

| Tool | Description |
|------|-------------|
| `cmw_set_signal_path` | Set measurement signal path scenario |
| `cmw_get_signal_path` | Get current signal path |
| `cmw_set_port` | Set generator/analyzer RF port |
| `cmw_system_all_off` | Turn off all generators and measurements |

### LTE Signaling (16 tools)

| Tool | Description |
|------|-------------|
| `cmw_lte_configure_cell` | Configure cell (band, BW, EARFCN, power) |
| `cmw_lte_cell_on` | Start base station emulation |
| `cmw_lte_cell_off` | Turn off LTE cell |
| `cmw_lte_configure_nas` | Configure NAS (MCC, MNC) |
| `cmw_lte_configure_bearer` | Configure EPS bearer (APN, IP version) |
| `cmw_lte_configure_cdrx` | Configure C-DRX |
| `cmw_lte_get_connection_state` | Get UE connection state |
| `cmw_lte_get_ue_info` | Get UE information |
| `cmw_lte_meas_configure` | Configure measurements (stat count, repetition) |
| `cmw_lte_meas_trigger` | Trigger multi-evaluation measurement |
| `cmw_lte_meas_fetch_power` | Fetch TX power results |
| `cmw_lte_meas_fetch_evm` | Fetch EVM results |
| `cmw_lte_meas_fetch_aclr` | Fetch ACLR results |
| `cmw_lte_meas_fetch_sem` | Fetch SEM results |
| `cmw_lte_meas_fetch_frequency_error` | Fetch frequency error results |
| `cmw_lte_meas_fetch_all` | Fetch all LTE results |

### WLAN Non-Signaling (11 tools)

| Tool | Description |
|------|-------------|
| `cmw_wlan_configure` | Configure WLAN measurement (standard, BW, freq, power) |
| `cmw_wlan_set_standard` | Set 802.11 standard (A/B/G/N/AC/AX) |
| `cmw_wlan_set_bandwidth` | Set channel bandwidth (20/40/80/160 MHz) |
| `cmw_wlan_set_frequency` | Set measurement frequency (Hz) |
| `cmw_wlan_set_expected_power` | Set expected input power (dBm) |
| `cmw_wlan_trigger` | Trigger measurement |
| `cmw_wlan_fetch_power` | Fetch TX power results |
| `cmw_wlan_fetch_evm` | Fetch EVM results |
| `cmw_wlan_fetch_spectrum_flatness` | Fetch spectrum flatness results |
| `cmw_wlan_fetch_frequency_error` | Fetch frequency error results |
| `cmw_wlan_fetch_all` | Fetch all WLAN results |

### Bluetooth/BLE Non-Signaling (11 tools)

| Tool | Description |
|------|-------------|
| `cmw_bt_configure` | Configure BT/BLE measurement |
| `cmw_bt_set_technology` | Set technology (Classic/LE) |
| `cmw_bt_set_ble_mode` | Set BLE PHY (1M/2M/Coded S2/S8) |
| `cmw_bt_set_packet_type` | Set Classic packet type (DH1-DH5) |
| `cmw_bt_set_frequency` | Set measurement frequency (Hz) |
| `cmw_bt_set_expected_power` | Set expected input power (dBm) |
| `cmw_bt_trigger` | Trigger measurement |
| `cmw_bt_fetch_power` | Fetch TX power results |
| `cmw_bt_fetch_modulation` | Fetch DEVM results |
| `cmw_bt_fetch_frequency` | Fetch frequency offset/drift results |
| `cmw_bt_fetch_all` | Fetch all BT results |

### SCPI (4 tools)

| Tool | Description |
|------|-------------|
| `cmw_scpi_send` | Send raw SCPI command (guarded) |
| `cmw_scpi_query` | Send SCPI query and return response (guarded) |
| `cmw_reset` | Reset to defaults (*RST) |
| `cmw_preset` | Full system preset |

### Templates (3 tools)

| Tool | Description |
|------|-------------|
| `cmw_list_templates` | List available measurement templates |
| `cmw_load_template` | Load a template by name |
| `cmw_apply_template` | Apply loaded template to CMW500 |

Available templates: `lte_tx_power`, `gprf_power`, `nonsig_rx`, `wlan_tx`, `wlan_rx`, `ble_tx`, `ble_rx`, `bt_classic_tx`

### State Management (3 tools)

| Tool | Description |
|------|-------------|
| `cmw_save_state` | Save current state to file |
| `cmw_load_state` | Load and restore state from file |
| `cmw_get_full_state` | Get current full configuration state |

### Limits (4 tools)

| Tool | Description |
|------|-------------|
| `cmw_define_limit` | Define a pass/fail limit |
| `cmw_check_limits` | Check values against defined limits |
| `cmw_list_limits` | List all defined limits |
| `cmw_clear_limits` | Clear all limits |

## Safety

The server enforces configurable safety limits to protect your equipment:

- **Generator power** -- bounded between `CMW_MIN_GENERATOR_POWER_DBM` and `CMW_MAX_GENERATOR_POWER_DBM`
- **Analyzer expected power** -- bounded by `CMW_MAX_EXPECTED_POWER_DBM`
- **Frequency range** -- bounded between `CMW_MIN_FREQUENCY_HZ` and `CMW_MAX_FREQUENCY_HZ`
- **SCPI sanitization** -- all parameters are validated against injection attacks
- **Raw SCPI** -- disabled by default; must explicitly enable `CMW_ALLOW_RAW_SCPI=true`
- **Path traversal** -- state file paths are validated against directory traversal

## Development

### Setup

```bash
git clone https://github.com/RFingAdam/mcp-rs-cmw500.git
cd mcp-rs-cmw500
uv pip install -e ".[dev]"
```

### Run Tests

```bash
# All unit tests (no hardware required)
uv run pytest tests/ -q

# Skip integration tests (default)
uv run pytest tests/ -m "not integration" -q

# With coverage
uv run pytest tests/ --cov=rs_cmw500_mcp --cov-report=term-missing
```

### Lint & Format

```bash
ruff check src/ tests/
ruff format src/ tests/
```

### Type Check

```bash
mypy src/rs_cmw500_mcp/
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

Apache 2.0 -- see [LICENSE](LICENSE).

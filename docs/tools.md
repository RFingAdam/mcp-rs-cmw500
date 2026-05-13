# Tools

This page documents the 79 MCP tools the server exposes. Tools are registered
under the `rs-cmw500` namespace when the server is loaded by an MCP client.

## Tool index

### Connection (6)

| Tool | Purpose |
| ---- | ------- |
| `cmw_discover` | Scan for CMW500 instruments on the network |
| `cmw_connect` | Connect to CMW500 at `host:port` |
| `cmw_disconnect` | Disconnect from CMW500 |
| `cmw_identify` | Get instrument ID (`*IDN?`) |
| `cmw_get_status` | Get connection and configuration status |
| `cmw_query_options` | Query installed hardware/software options |

### GPRF Generator (7)

| Tool | Purpose |
| ---- | ------- |
| `cmw_gen_set_frequency` | Set output frequency (Hz) |
| `cmw_gen_set_level` | Set output level (dBm) |
| `cmw_gen_output_on` | Enable RF output |
| `cmw_gen_output_off` | Disable RF output |
| `cmw_gen_load_arb` | Load ARB waveform file |
| `cmw_gen_configure_arb` | Configure ARB playback mode |
| `cmw_gen_set_baseband_mode` | Set baseband mode (CW / ARB) |

### GPRF Analyzer (10)

| Tool | Purpose |
| ---- | ------- |
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

### GPRF Signal Path (4)

| Tool | Purpose |
| ---- | ------- |
| `cmw_set_signal_path` | Set measurement signal path scenario |
| `cmw_get_signal_path` | Get current signal path |
| `cmw_set_port` | Set generator/analyzer RF port |
| `cmw_system_all_off` | Turn off all generators and measurements |

### LTE Signaling (16)

| Tool | Purpose |
| ---- | ------- |
| `cmw_lte_configure_cell` | Configure cell (band, BW, EARFCN, power) |
| `cmw_lte_cell_on` | Start base-station emulation |
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
| `cmw_lte_meas_fetch_all` | Fetch all LTE results in one call |

### WLAN Non-Signaling (11)

| Tool | Purpose |
| ---- | ------- |
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
| `cmw_wlan_fetch_all` | Fetch all WLAN results in one call |

### Bluetooth / BLE Non-Signaling (11)

| Tool | Purpose |
| ---- | ------- |
| `cmw_bt_configure` | Configure BT/BLE measurement |
| `cmw_bt_set_technology` | Set technology (Classic / LE) |
| `cmw_bt_set_ble_mode` | Set BLE PHY (1M / 2M / Coded S2 / S8) |
| `cmw_bt_set_packet_type` | Set Classic packet type (DH1-DH5) |
| `cmw_bt_set_frequency` | Set measurement frequency (Hz) |
| `cmw_bt_set_expected_power` | Set expected input power (dBm) |
| `cmw_bt_trigger` | Trigger measurement |
| `cmw_bt_fetch_power` | Fetch TX power results |
| `cmw_bt_fetch_modulation` | Fetch DEVM results |
| `cmw_bt_fetch_frequency` | Fetch frequency offset / drift results |
| `cmw_bt_fetch_all` | Fetch all BT results in one call |

### SCPI (4)

| Tool | Purpose |
| ---- | ------- |
| `cmw_scpi_send` | Send raw SCPI command (guarded) |
| `cmw_scpi_query` | Send SCPI query and return response (guarded) |
| `cmw_reset` | Reset to defaults (`*RST`) |
| `cmw_preset` | Full system preset |

### Templates (3)

| Tool | Purpose |
| ---- | ------- |
| `cmw_list_templates` | List available measurement templates |
| `cmw_load_template` | Load a template by name |
| `cmw_apply_template` | Apply loaded template to CMW500 |

Available templates: `lte_tx_power`, `gprf_power`, `nonsig_rx`, `wlan_tx`,
`wlan_rx`, `ble_tx`, `ble_rx`, `bt_classic_tx`.

### State (3)

| Tool | Purpose |
| ---- | ------- |
| `cmw_save_state` | Save current state to file |
| `cmw_load_state` | Load and restore state from file |
| `cmw_get_full_state` | Get current full configuration state |

### Limits (4)

| Tool | Purpose |
| ---- | ------- |
| `cmw_define_limit` | Define a pass/fail limit |
| `cmw_check_limits` | Check values against defined limits |
| `cmw_list_limits` | List all defined limits |
| `cmw_clear_limits` | Clear all limits |

---

## Source of truth

Tool definitions live in
[`src/rs_cmw500_mcp/tools/`](../src/rs_cmw500_mcp/tools/), one module per
domain. Each tool has a complete JSON-Schema `inputSchema` declared at
registration — arguments, defaults, and units are documented inline there.

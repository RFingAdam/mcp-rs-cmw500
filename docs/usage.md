# Usage

A practical end-to-end walkthrough. For the full tool reference, see [Tools](tools.md).

---

## Scenario: LTE TX measurement for Band 7, 20 MHz

You have an LTE UE on the bench. You want to bring up a base-station-emulator
cell on Band 7 EARFCN 3100, attach the UE, then sweep TX power, EVM, ACLR,
SEM, and frequency error.

## Setup

```bash
uv pip install -e ".[dev]"
```

Register the MCP server with Claude Desktop:

```json
{
  "mcpServers": {
    "rs-cmw500": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/mcp-rs-cmw500",
        "run", "rs-cmw500-mcp"
      ]
    }
  }
}
```

Set the CMW500 host in `.env`:

```bash
CMW_DEFAULT_HOST=192.168.1.100
```

Restart your MCP client.

## Step 1 — connect

> *"Connect to the CMW500 and tell me what options it has."*

The agent calls `cmw_connect`, `cmw_identify`, `cmw_query_options`:

```json
{
  "manufacturer": "Rohde&Schwarz",
  "model": "CMW500",
  "options": ["KS300", "KS301", "KS400", "KS600"]
}
```

## Step 2 — configure the cell

> *"Bring up an LTE cell on band 7, 20 MHz, EARFCN 3100, DL power −70 dBm. Use the lte_tx_power template."*

```
cmw_lte_configure_cell(band=7, bandwidth_mhz=20, earfcn=3100, dl_power_dbm=-70)
cmw_lte_cell_on()
cmw_load_template(name="lte_tx_power")
cmw_apply_template()
```

## Step 3 — wait for attach

> *"Poll the connection state until the UE is connected."*

The agent loops `cmw_lte_get_connection_state` until it returns:

```json
{ "state": "Connected", "rrc_state": "RRC_CONNECTED" }
```

`cmw_lte_get_ue_info` returns the IMSI / IMEI / capability set.

## Step 4 — measure

> *"Configure for 10 measurement repetitions, trigger, and fetch all results."*

```
cmw_lte_meas_configure(stat_count=10, repetition="SINGleshot")
cmw_lte_meas_trigger()
cmw_lte_meas_fetch_all()
```

Returns:

```json
{
  "power_dbm": 22.4,
  "evm_rms_pct": 1.8,
  "evm_peak_pct": 5.6,
  "frequency_error_hz": 12.3,
  "aclr_lower_dbc": -42.1,
  "aclr_upper_dbc": -41.8,
  "sem_pass": true
}
```

## Step 5 — pass/fail and save

> *"Check those against 3GPP TS 36.521 limits for Band 7, then save state."*

If you've previously seeded the limits via `cmw_define_limit`,
`cmw_check_limits` returns a structured pass/fail report. Then
`cmw_save_state(path="band7_20mhz_run01.json")` snapshots the full CMW500
configuration for replay.

---

## What just happened

Five plain-English turns drove a full LTE TX compliance run — cell setup,
UE attach, measurement, pass/fail, state snapshot — without you writing a
single SCPI line. The state file is now a portable replay artifact that the
next AI session can `cmw_load_state` and re-run.

- For more tools: [Tool reference](tools.md)
- For how this fits in the suite: [Architecture](architecture.md)
- For sibling MCPs that compose with this one: [eng-mcp-suite catalog](https://github.com/RFingAdam/eng-mcp-suite#whats-included)

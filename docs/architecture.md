# Architecture

## Internal layout

```
┌──────────────────────────────────────────────────────────────────┐
│  User-facing surfaces                                            │
│  ┌────────────────────┐              ┌────────────────────────┐  │
│  │  MCP server        │              │  Python API:           │  │
│  │  (stdio transport) │              │  import rs_cmw500_mcp  │  │
│  └────────────────────┘              └────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────────┐
│  Orchestration — tools/ (79 tools, 5 domains)                    │
│  • connection                                                    │
│  • gprf / gprf_advanced     (generator, analyzer, signal-path)   │
│  • lte                       (signaling)                         │
│  • wlan                      (non-signaling)                     │
│  • bluetooth                 (Classic + BLE non-signaling)       │
│  • scpi · templates · state · limits · shared                    │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────────┐
│  Driver / transport                                              │
│  • driver/cmw500_driver.py  — SCPI command layer (GPRF, LTE, …)  │
│  • driver/scpi_socket.py    — async TCP/IP transport             │
│  • safety/validators.py     — RF limit enforcement, SCPI sanitize│
└──────────────────────────────────────────────────────────────────┘
                              │
                  TCP/IP SCPI (default port 5025)
                              │
                              ▼
                    R&S CMW500 instrument
```

Concurrent tool calls are serialized per-connection by `asyncio.Lock` to keep
SCPI framing intact. The driver is fully asyncio-native; the GPRF generator
and analyzer can run concurrently as long as they're on different RF ports.

## Source layout

```
mcp-rs-cmw500/
├── src/rs_cmw500_mcp/
│   ├── server.py            # MCP server (stdio transport)
│   ├── config.py            # pydantic-settings
│   ├── exceptions.py
│   ├── driver/
│   │   ├── cmw500_driver.py
│   │   └── scpi_socket.py
│   ├── models/
│   │   └── cmw_types.py     # Enums, configs, result dataclasses
│   ├── tools/               # 79 MCP tool definitions
│   │   ├── registry.py
│   │   ├── shared.py        # Connection pool, locks
│   │   ├── connection.py
│   │   ├── gprf.py
│   │   ├── gprf_advanced.py
│   │   ├── lte.py
│   │   ├── wlan.py
│   │   ├── bluetooth.py
│   │   ├── scpi.py
│   │   ├── templates_tools.py
│   │   ├── limits_tools.py
│   │   └── state_tools.py
│   ├── templates/           # Pre-built measurement configs
│   ├── safety/              # RF limits + SCPI sanitize
│   ├── limits.py
│   └── state.py
├── tests/
└── docs/
```

## Position in eng-mcp-suite

`mcp-rs-cmw500` sits in the **lab-gear** layer — it talks to a physical
radio-comms tester over SCPI.

```
        ┌─────────────────────────────────────┐
        │   AI agent (Claude Code / Desktop)  │
        └──────┬──────────────┬───────────────┘
               │ via MCP      │ via MCP
       ┌───────▼──────────┐ ┌─▼──────────────────────┐
       │ mcp-rs-cmw500    │ │ siblings: vna, spectrum-analyzer, siggen │
       └───────┬──────────┘ └────────────────────────┘
               │ TX/RX results JSON
       ┌───────▼──────────────────────┐
       │  downstream consumers:       │
       │  mcp-emc-regulations         │
       └──────────────────────────────┘
```

### Feeds (this MCP produces output that)…

- **mcp-emc-regulations** — LTE TX power / EVM / ACLR / SEM results cross-
  reference against 3GPP TS 36.521 / regional limits.

### Consumes (this MCP accepts input from)…

- **mcp-rs-siggen** — coordinated stimulus for RX sensitivity sweeps.
- **mcp-emc-regulations** — limit definitions for `cmw_define_limit`.

### Workflow bundles that include this MCP

| Bundle                  | Role of this MCP                                 |
| ----------------------- | ------------------------------------------------ |
| `lab-automation`        | Radio-comms tester leg for cellular/Wi-Fi DUTs   |
| `cellular-compliance`   | 3GPP TS 36.521 LTE test cases                    |

---

## Design decisions

- **Direct SCPI, no CMWrun.** The CMW500 exposes the same SCPI surface
  CMWrun uses internally — talking to it directly drops a costly software
  dependency.
- **Per-domain tool modules.** LTE, WLAN, BT each get their own tool module
  so domain-specific argument types stay close to the SCPI dialect they map
  to.
- **Safety limits in the driver.** Power and frequency clamps live below the
  tool layer so even raw SCPI can't drive the CMW500 past safe input/output
  bounds.
- **Raw SCPI off by default.** Shared-bench setups demand opt-in; we default
  to closed and require `CMW_ALLOW_RAW_SCPI=true` to unlock.

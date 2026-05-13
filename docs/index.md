# mcp-rs-cmw500

**Drive the Rohde & Schwarz CMW500 Wideband Radio Communication Tester from any MCP-compatible AI client.**
**Direct TCP/IP SCPI (port 5025) — 79 tools across LTE signaling, WLAN, Bluetooth/BLE, and GPRF.**

---

## What it is

`mcp-rs-cmw500` is a [Model Context Protocol](https://modelcontextprotocol.io)
server that automates the R&S CMW500 over direct TCP/IP SCPI. No CMWrun,
no NI-VISA, no vendor middleware — your AI agent talks SCPI to the CMW500
the same way a Python script would.

The server covers five RF technology domains: LTE signaling, WLAN
non-signaling, Bluetooth/BLE non-signaling, GPRF generator/analyzer, and
shared signal-path control.

## Install

```bash
git clone https://github.com/RFingAdam/mcp-rs-cmw500.git
cd mcp-rs-cmw500
uv pip install -e ".[dev]"
```

## First call

=== "MCP"

    Add to `claude_desktop_config.json`:

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

    Then ask your assistant:

    > *"Bring up a 20 MHz LTE cell on band 7 EARFCN 3100, wait for UE attach, and run TX power + EVM + ACLR + SEM."*

=== "Python"

    ```python
    import asyncio
    from rs_cmw500_mcp.driver import CMW500Driver

    async def main():
        async with CMW500Driver("192.168.1.100", 5025) as cmw:
            await cmw.lte_configure_cell(band=7, bandwidth_mhz=20,
                                         earfcn=3100, dl_power_dbm=-70)
            await cmw.lte_cell_on()

    asyncio.run(main())
    ```

## Where to next

- [Tool reference](tools.md) — every MCP tool with arguments
- [Usage examples](usage.md) — an LTE TX measurement walkthrough
- [Architecture](architecture.md) — how this MCP fits inside eng-mcp-suite

---

!!! note "Part of eng-mcp-suite"
    This MCP server is part of [eng-mcp-suite](https://github.com/RFingAdam/eng-mcp-suite) —
    an umbrella of engineering MCP servers across RF, EMC, PCB, signal
    integrity, EM simulation, and lab test.

# R&S CMW500 MCP Server

MCP server for Rohde & Schwarz CMW500 Wideband Radio Communication Tester automation via TCP/IP SCPI.

## Features

- GPRF Generator control (frequency, level, ARB waveforms)
- GPRF Analyzer measurements (power, spectrum)
- LTE signaling mode (cell configuration, connection management)
- LTE measurements (power, EVM, ACLR, SEM)
- Safety limits to protect DUT
- Measurement templates for common test scenarios
- State save/restore for reproducible measurements
- Pass/fail limit checking

## Installation

```bash
uv pip install -e ".[dev]"
```

## Usage

```bash
rs-cmw500-mcp
```

## Configuration

Copy `.env.example` to `.env` and adjust settings. All settings use the `CMW_` prefix.

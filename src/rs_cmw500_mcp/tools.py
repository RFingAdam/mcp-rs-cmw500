"""MCP tool definitions and handlers for CMW500 operations."""

import json
import logging
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool

from .config import get_settings
from .driver import CMW500Driver
from .exceptions import CMW500Error
from .limits import LimitLine, LimitManager, LimitSegment
from .models.cmw_types import (
    ARBRepetition,
    CellConfig,
    MeasRepetition,
    SignalPath,
)
from .state import InstrumentState, StateManager
from .templates import (
    GPRFPowerTemplate,
    LTETxPowerTemplate,
    MeasurementTemplate,
    NonSignalingRxTemplate,
    WLANTxTemplate,
)

logger = logging.getLogger(__name__)

# Global CMW500 connection manager
_cmw_connections: dict[str, CMW500Driver] = {}

# Global template storage
_current_template: MeasurementTemplate | None = None

# Global limit manager
_limit_manager = LimitManager()

# Global state manager
_state_manager = StateManager()

# Template registry
_template_registry: dict[str, type] = {
    "lte_tx_power": LTETxPowerTemplate,
    "gprf_power": GPRFPowerTemplate,
    "nonsig_rx": NonSignalingRxTemplate,
    "wlan_tx": WLANTxTemplate,
}


def _get_connection_key(host: str, port: int) -> str:
    """Generate unique key for connection."""
    return f"{host}:{port}"


async def _get_cmw(
    host: str | None = None, port: int | None = None
) -> CMW500Driver:
    """Get or create CMW500 connection."""
    settings = get_settings()
    host = host or settings.default_host
    port = port or settings.default_port
    key = _get_connection_key(host, port)

    if key in _cmw_connections:
        cmw = _cmw_connections[key]
        if cmw.is_connected:
            return cmw
        # Clean up stale connection
        try:
            await cmw.disconnect()
        except Exception:
            pass

    # Create new connection
    cmw = CMW500Driver(
        host=host,
        port=port,
        timeout=settings.connection_timeout,
        command_timeout=settings.command_timeout,
        safety_limits=settings.get_safety_limits(),
    )
    await cmw.connect()
    _cmw_connections[key] = cmw
    return cmw


async def _close_cmw(host: str, port: int) -> bool:
    """Close CMW500 connection."""
    key = _get_connection_key(host, port)
    if key in _cmw_connections:
        cmw = _cmw_connections.pop(key)
        await cmw.disconnect()
        return True
    return False


def _format_result(result: Any) -> list[TextContent]:
    """Format result as MCP TextContent."""
    if isinstance(result, dict):
        text = json.dumps(result, indent=2, default=str)
    elif isinstance(result, list):
        text = json.dumps(result, indent=2, default=str)
    else:
        text = str(result)
    return [TextContent(type="text", text=text)]


def _format_error(error: Exception) -> list[TextContent]:
    """Format error as MCP TextContent."""
    return [TextContent(type="text", text=f"Error: {error}")]


# =============================================================================
# Tool Definitions
# =============================================================================


def get_tools() -> list[Tool]:
    """Get all MCP tool definitions."""
    return [
        # =====================================================================
        # Connection Tools
        # =====================================================================
        Tool(
            name="cmw_discover",
            description="Scan for CMW500 instruments on the network (port 5025)",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Host to scan (default: 127.0.0.1)",
                        "default": "127.0.0.1",
                    },
                    "start_port": {
                        "type": "integer",
                        "description": "Start port (default: 5025)",
                        "default": 5025,
                    },
                    "end_port": {
                        "type": "integer",
                        "description": "End port (default: 5030)",
                        "default": 5030,
                    },
                },
            },
        ),
        Tool(
            name="cmw_connect",
            description="Connect to CMW500 at specified host:port",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "CMW500 hostname or IP (default: from config)",
                    },
                    "port": {
                        "type": "integer",
                        "description": "TCP port (default: 5025)",
                    },
                },
            },
        ),
        Tool(
            name="cmw_disconnect",
            description="Disconnect from CMW500",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_identify",
            description="Get CMW500 identification (*IDN?): manufacturer, model, serial, firmware",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_get_status",
            description="Get CMW500 connection and configuration status",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_query_options",
            description="Query installed hardware and software options",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        # =====================================================================
        # GPRF Generator Tools
        # =====================================================================
        Tool(
            name="cmw_gen_set_frequency",
            description="Set GPRF generator output frequency in Hz",
            inputSchema={
                "type": "object",
                "properties": {
                    "frequency_hz": {
                        "type": "number",
                        "description": "Frequency in Hz (70 MHz to 6 GHz)",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["frequency_hz"],
            },
        ),
        Tool(
            name="cmw_gen_set_level",
            description="Set GPRF generator output level in dBm",
            inputSchema={
                "type": "object",
                "properties": {
                    "level_dbm": {
                        "type": "number",
                        "description": "Output level in dBm (-130 to 0)",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["level_dbm"],
            },
        ),
        Tool(
            name="cmw_gen_output_on",
            description="Enable GPRF generator RF output",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_gen_output_off",
            description="Disable GPRF generator RF output (safe state)",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_gen_load_arb",
            description="Load ARB waveform file on CMW500 generator",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to ARB file on CMW500 filesystem",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="cmw_gen_configure_arb",
            description="Configure ARB waveform playback mode (continuous/single)",
            inputSchema={
                "type": "object",
                "properties": {
                    "repetition": {
                        "type": "string",
                        "description": "Repetition mode",
                        "enum": ["continuous", "single"],
                        "default": "continuous",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        # =====================================================================
        # GPRF Analyzer Tools
        # =====================================================================
        Tool(
            name="cmw_meas_configure_power",
            description="Configure GPRF power measurement parameters",
            inputSchema={
                "type": "object",
                "properties": {
                    "statistic_count": {
                        "type": "integer",
                        "description": "Number of measurements for statistics (default: 10)",
                        "default": 10,
                    },
                    "meas_length_s": {
                        "type": "number",
                        "description": "Measurement length in seconds (default: 0.001)",
                        "default": 0.001,
                    },
                    "repetition": {
                        "type": "string",
                        "description": "Repetition mode",
                        "enum": ["singleshot", "continuous"],
                        "default": "singleshot",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_meas_configure_spectrum",
            description="Configure GPRF spectrum measurement",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_meas_set_frequency",
            description="Set GPRF analyzer measurement frequency in Hz",
            inputSchema={
                "type": "object",
                "properties": {
                    "frequency_hz": {
                        "type": "number",
                        "description": "Frequency in Hz",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["frequency_hz"],
            },
        ),
        Tool(
            name="cmw_meas_set_expected_power",
            description="Set expected input power for GPRF analyzer in dBm",
            inputSchema={
                "type": "object",
                "properties": {
                    "power_dbm": {
                        "type": "number",
                        "description": "Expected power in dBm",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["power_dbm"],
            },
        ),
        Tool(
            name="cmw_meas_trigger",
            description="Trigger GPRF power measurement",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_meas_fetch_power",
            description="Fetch GPRF power measurement results (current, average, max, min)",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_meas_fetch_spectrum",
            description="Fetch GPRF spectrum measurement results",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        # =====================================================================
        # LTE Signaling Tools
        # =====================================================================
        Tool(
            name="cmw_lte_configure_cell",
            description="Configure LTE cell parameters (band, BW, EARFCN, DL level)",
            inputSchema={
                "type": "object",
                "properties": {
                    "band": {
                        "type": "integer",
                        "description": "LTE band number (e.g., 1, 3, 7, 41)",
                    },
                    "bandwidth_mhz": {
                        "type": "number",
                        "description": "Channel bandwidth in MHz (1.4, 3, 5, 10, 15, 20)",
                        "enum": [1.4, 3, 5, 10, 15, 20],
                    },
                    "dl_earfcn": {
                        "type": "integer",
                        "description": "Downlink EARFCN channel number",
                    },
                    "dl_level_dbm": {
                        "type": "number",
                        "description": "Downlink signal level in dBm (default: -60)",
                        "default": -60,
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["band", "bandwidth_mhz", "dl_earfcn"],
            },
        ),
        Tool(
            name="cmw_lte_cell_on",
            description="Turn on LTE cell (start base station emulation)",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_cell_off",
            description="Turn off LTE cell",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_get_connection_state",
            description="Get LTE UE connection state (ATT, CONN, IDLE, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_configure_nas",
            description="Configure LTE NAS parameters (MCC, MNC)",
            inputSchema={
                "type": "object",
                "properties": {
                    "mcc": {
                        "type": "string",
                        "description": "Mobile Country Code (default: 001)",
                        "default": "001",
                    },
                    "mnc": {
                        "type": "string",
                        "description": "Mobile Network Code (default: 01)",
                        "default": "01",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_configure_bearer",
            description="Configure default EPS bearer",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_configure_cdrx",
            description="Configure Connected DRX (C-DRX) enable/disable",
            inputSchema={
                "type": "object",
                "properties": {
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable C-DRX (default: false)",
                        "default": False,
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_get_ue_info",
            description="Get UE (User Equipment) information including connection state",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        # =====================================================================
        # LTE Measurement Tools
        # =====================================================================
        Tool(
            name="cmw_lte_meas_configure",
            description="Configure LTE multi-evaluation measurement",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_meas_trigger",
            description="Trigger LTE multi-evaluation measurement",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_meas_fetch_power",
            description="Fetch LTE TX power measurement results",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_meas_fetch_evm",
            description="Fetch LTE EVM (Error Vector Magnitude) measurement results",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_meas_fetch_aclr",
            description="Fetch LTE ACLR (Adjacent Channel Leakage Ratio) measurement results",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_meas_fetch_sem",
            description="Fetch LTE SEM (Spectrum Emission Mask) measurement results",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_meas_fetch_frequency_error",
            description="Fetch LTE frequency error measurement results",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_lte_meas_fetch_all",
            description="Fetch all LTE measurement results (power, EVM, ACLR, SEM)",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        # =====================================================================
        # Route / Signal Path Tools
        # =====================================================================
        Tool(
            name="cmw_set_signal_path",
            description="Set GPRF measurement signal path scenario (standalone or combined)",
            inputSchema={
                "type": "object",
                "properties": {
                    "scenario": {
                        "type": "string",
                        "description": "Signal path scenario",
                        "enum": ["standalone", "cspath"],
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["scenario"],
            },
        ),
        Tool(
            name="cmw_get_signal_path",
            description="Get current GPRF signal path scenario",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        # =====================================================================
        # Raw SCPI Tools
        # =====================================================================
        Tool(
            name="cmw_scpi_send",
            description="Send raw SCPI command to CMW500 (no response)",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "SCPI command string",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="cmw_scpi_query",
            description="Send SCPI query and return response",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "SCPI query (should end with ?)",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="cmw_reset",
            description="Reset CMW500 to default state (*RST)",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="cmw_preset",
            description="Full system preset of CMW500",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        # =====================================================================
        # Template Tools
        # =====================================================================
        Tool(
            name="cmw_list_templates",
            description="List available measurement templates",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="cmw_load_template",
            description="Load a measurement template by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "string",
                        "description": "Template name",
                        "enum": ["lte_tx_power", "gprf_power", "nonsig_rx", "wlan_tx"],
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Optional parameter overrides",
                    },
                },
                "required": ["template_name"],
            },
        ),
        Tool(
            name="cmw_apply_template",
            description="Apply currently loaded template to CMW500",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        # =====================================================================
        # Limit Tools
        # =====================================================================
        Tool(
            name="cmw_define_limit",
            description="Define a pass/fail limit for measurement checking",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Limit name",
                    },
                    "parameter": {
                        "type": "string",
                        "description": "Parameter name to check (e.g., power_dbm, evm_percent)",
                    },
                    "max_value": {
                        "type": "number",
                        "description": "Maximum allowed value",
                    },
                    "min_value": {
                        "type": "number",
                        "description": "Minimum allowed value",
                    },
                    "unit": {
                        "type": "string",
                        "description": "Unit of measurement (e.g., dBm, %)",
                        "default": "",
                    },
                },
                "required": ["name", "parameter"],
            },
        ),
        Tool(
            name="cmw_check_limits",
            description="Check measurement values against defined limits",
            inputSchema={
                "type": "object",
                "properties": {
                    "measurements": {
                        "type": "object",
                        "description": "Dictionary of parameter:value pairs to check",
                    },
                },
                "required": ["measurements"],
            },
        ),
        Tool(
            name="cmw_clear_limits",
            description="Clear all defined limits",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="cmw_list_limits",
            description="List all defined limits",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        # =====================================================================
        # State Tools
        # =====================================================================
        Tool(
            name="cmw_save_state",
            description="Save current CMW500 state to file",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "State filename (without .json extension)",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes about this state",
                        "default": "",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["filename"],
            },
        ),
        Tool(
            name="cmw_load_state",
            description="Load and restore CMW500 state from file",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "State filename (without .json extension)",
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["filename"],
            },
        ),
        Tool(
            name="cmw_get_full_state",
            description="Get current CMW500 full configuration state",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
    ]


# =============================================================================
# Tool Handlers
# =============================================================================


async def handle_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Handle tool invocation.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        List of TextContent with results
    """
    try:
        # Connection Tools
        if name == "cmw_discover":
            return await _handle_discover(arguments)
        elif name == "cmw_connect":
            return await _handle_connect(arguments)
        elif name == "cmw_disconnect":
            return await _handle_disconnect(arguments)
        elif name == "cmw_identify":
            return await _handle_identify(arguments)
        elif name == "cmw_get_status":
            return await _handle_get_status(arguments)
        elif name == "cmw_query_options":
            return await _handle_query_options(arguments)

        # GPRF Generator Tools
        elif name == "cmw_gen_set_frequency":
            return await _handle_gen_set_frequency(arguments)
        elif name == "cmw_gen_set_level":
            return await _handle_gen_set_level(arguments)
        elif name == "cmw_gen_output_on":
            return await _handle_gen_output_on(arguments)
        elif name == "cmw_gen_output_off":
            return await _handle_gen_output_off(arguments)
        elif name == "cmw_gen_load_arb":
            return await _handle_gen_load_arb(arguments)
        elif name == "cmw_gen_configure_arb":
            return await _handle_gen_configure_arb(arguments)

        # GPRF Analyzer Tools
        elif name == "cmw_meas_configure_power":
            return await _handle_meas_configure_power(arguments)
        elif name == "cmw_meas_configure_spectrum":
            return await _handle_meas_configure_spectrum(arguments)
        elif name == "cmw_meas_set_frequency":
            return await _handle_meas_set_frequency(arguments)
        elif name == "cmw_meas_set_expected_power":
            return await _handle_meas_set_expected_power(arguments)
        elif name == "cmw_meas_trigger":
            return await _handle_meas_trigger(arguments)
        elif name == "cmw_meas_fetch_power":
            return await _handle_meas_fetch_power(arguments)
        elif name == "cmw_meas_fetch_spectrum":
            return await _handle_meas_fetch_spectrum(arguments)

        # LTE Signaling Tools
        elif name == "cmw_lte_configure_cell":
            return await _handle_lte_configure_cell(arguments)
        elif name == "cmw_lte_cell_on":
            return await _handle_lte_cell_on(arguments)
        elif name == "cmw_lte_cell_off":
            return await _handle_lte_cell_off(arguments)
        elif name == "cmw_lte_get_connection_state":
            return await _handle_lte_get_connection_state(arguments)
        elif name == "cmw_lte_configure_nas":
            return await _handle_lte_configure_nas(arguments)
        elif name == "cmw_lte_configure_bearer":
            return await _handle_lte_configure_bearer(arguments)
        elif name == "cmw_lte_configure_cdrx":
            return await _handle_lte_configure_cdrx(arguments)
        elif name == "cmw_lte_get_ue_info":
            return await _handle_lte_get_ue_info(arguments)

        # LTE Measurement Tools
        elif name == "cmw_lte_meas_configure":
            return await _handle_lte_meas_configure(arguments)
        elif name == "cmw_lte_meas_trigger":
            return await _handle_lte_meas_trigger(arguments)
        elif name == "cmw_lte_meas_fetch_power":
            return await _handle_lte_meas_fetch_power(arguments)
        elif name == "cmw_lte_meas_fetch_evm":
            return await _handle_lte_meas_fetch_evm(arguments)
        elif name == "cmw_lte_meas_fetch_aclr":
            return await _handle_lte_meas_fetch_aclr(arguments)
        elif name == "cmw_lte_meas_fetch_sem":
            return await _handle_lte_meas_fetch_sem(arguments)
        elif name == "cmw_lte_meas_fetch_frequency_error":
            return await _handle_lte_meas_fetch_frequency_error(arguments)
        elif name == "cmw_lte_meas_fetch_all":
            return await _handle_lte_meas_fetch_all(arguments)

        # Route Tools
        elif name == "cmw_set_signal_path":
            return await _handle_set_signal_path(arguments)
        elif name == "cmw_get_signal_path":
            return await _handle_get_signal_path(arguments)

        # Raw SCPI Tools
        elif name == "cmw_scpi_send":
            return await _handle_scpi_send(arguments)
        elif name == "cmw_scpi_query":
            return await _handle_scpi_query(arguments)
        elif name == "cmw_reset":
            return await _handle_reset(arguments)
        elif name == "cmw_preset":
            return await _handle_preset(arguments)

        # Template Tools
        elif name == "cmw_list_templates":
            return await _handle_list_templates(arguments)
        elif name == "cmw_load_template":
            return await _handle_load_template(arguments)
        elif name == "cmw_apply_template":
            return await _handle_apply_template(arguments)

        # Limit Tools
        elif name == "cmw_define_limit":
            return await _handle_define_limit(arguments)
        elif name == "cmw_check_limits":
            return await _handle_check_limits(arguments)
        elif name == "cmw_clear_limits":
            return await _handle_clear_limits(arguments)
        elif name == "cmw_list_limits":
            return await _handle_list_limits(arguments)

        # State Tools
        elif name == "cmw_save_state":
            return await _handle_save_state(arguments)
        elif name == "cmw_load_state":
            return await _handle_load_state(arguments)
        elif name == "cmw_get_full_state":
            return await _handle_get_full_state(arguments)

        else:
            return _format_error(ValueError(f"Unknown tool: {name}"))

    except CMW500Error as e:
        logger.error(f"CMW500 error in {name}: {e}")
        return _format_error(e)
    except Exception as e:
        logger.error(f"Unexpected error in {name}: {e}")
        return _format_error(e)


# =============================================================================
# Handler Implementations
# =============================================================================


async def _handle_discover(args: dict[str, Any]) -> list[TextContent]:
    """Scan for CMW500 instruments."""
    host = args.get("host", "127.0.0.1")
    start_port = args.get("start_port", 5025)
    end_port = args.get("end_port", 5030)

    found = []
    for port in range(start_port, end_port + 1):
        try:
            cmw = CMW500Driver(host=host, port=port, timeout=2.0)
            await cmw.connect()
            info = await cmw.identify()
            found.append({
                "host": host,
                "port": port,
                "model": info.model,
                "serial": info.serial_number,
                "firmware": info.firmware_version,
            })
            await cmw.disconnect()
        except Exception:
            continue

    return _format_result({
        "scan_range": f"{host}:{start_port}-{end_port}",
        "instruments_found": len(found),
        "instruments": found,
    })


async def _handle_connect(args: dict[str, Any]) -> list[TextContent]:
    """Connect to CMW500."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    info = await cmw.identify()
    return _format_result({
        "status": "connected",
        "address": cmw._scpi.address,
        "instrument": info.to_dict(),
    })


async def _handle_disconnect(args: dict[str, Any]) -> list[TextContent]:
    """Disconnect from CMW500."""
    settings = get_settings()
    host = args.get("host", settings.default_host)
    port = args.get("port", settings.default_port)
    closed = await _close_cmw(host, port)
    return _format_result({
        "status": "disconnected" if closed else "not_connected",
        "address": f"{host}:{port}",
    })


async def _handle_identify(args: dict[str, Any]) -> list[TextContent]:
    """Get CMW500 identification."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    info = await cmw.identify()
    return _format_result(info.to_dict())


async def _handle_get_status(args: dict[str, Any]) -> list[TextContent]:
    """Get CMW500 status."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    status = await cmw.get_status()
    return _format_result(status)


async def _handle_query_options(args: dict[str, Any]) -> list[TextContent]:
    """Query installed options."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    options = await cmw.query_options()
    return _format_result({"options": options, "count": len(options)})


async def _handle_gen_set_frequency(args: dict[str, Any]) -> list[TextContent]:
    """Set generator frequency."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    freq = args["frequency_hz"]
    await cmw.gen_set_frequency(freq)
    return _format_result({
        "status": "ok",
        "frequency_hz": freq,
        "frequency_mhz": freq / 1e6,
    })


async def _handle_gen_set_level(args: dict[str, Any]) -> list[TextContent]:
    """Set generator level."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    level = args["level_dbm"]
    await cmw.gen_set_level(level)
    return _format_result({"status": "ok", "level_dbm": level})


async def _handle_gen_output_on(args: dict[str, Any]) -> list[TextContent]:
    """Enable generator output."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.gen_output_on()
    return _format_result({"status": "ok", "generator_output": "ON"})


async def _handle_gen_output_off(args: dict[str, Any]) -> list[TextContent]:
    """Disable generator output."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.gen_output_off()
    return _format_result({"status": "ok", "generator_output": "OFF"})


async def _handle_gen_load_arb(args: dict[str, Any]) -> list[TextContent]:
    """Load ARB file."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    file_path = args["file_path"]
    await cmw.gen_load_arb(file_path)
    return _format_result({"status": "ok", "arb_file": file_path})


async def _handle_gen_configure_arb(args: dict[str, Any]) -> list[TextContent]:
    """Configure ARB playback."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    rep = args.get("repetition", "continuous")
    arb_rep = (
        ARBRepetition.CONTINUOUS if rep == "continuous" else ARBRepetition.SINGLE
    )
    await cmw.gen_configure_arb(arb_rep)
    return _format_result({"status": "ok", "repetition": rep})


async def _handle_meas_configure_power(args: dict[str, Any]) -> list[TextContent]:
    """Configure power measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    rep_str = args.get("repetition", "singleshot")
    rep = (
        MeasRepetition.SINGLESHOT
        if rep_str == "singleshot"
        else MeasRepetition.CONTINUOUS
    )
    await cmw.meas_configure_power(
        statistic_count=args.get("statistic_count", 10),
        meas_length_s=args.get("meas_length_s", 0.001),
        repetition=rep,
    )
    return _format_result({"status": "ok", "measurement": "power_configured"})


async def _handle_meas_configure_spectrum(args: dict[str, Any]) -> list[TextContent]:
    """Configure spectrum measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.meas_configure_spectrum()
    return _format_result(result)


async def _handle_meas_set_frequency(args: dict[str, Any]) -> list[TextContent]:
    """Set analyzer frequency."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    freq = args["frequency_hz"]
    await cmw.meas_set_frequency(freq)
    return _format_result({
        "status": "ok",
        "frequency_hz": freq,
        "frequency_mhz": freq / 1e6,
    })


async def _handle_meas_set_expected_power(args: dict[str, Any]) -> list[TextContent]:
    """Set expected power."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    power = args["power_dbm"]
    await cmw.meas_set_expected_power(power)
    return _format_result({"status": "ok", "expected_power_dbm": power})


async def _handle_meas_trigger(args: dict[str, Any]) -> list[TextContent]:
    """Trigger power measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.meas_trigger_power()
    return _format_result({"status": "ok", "measurement": "triggered"})


async def _handle_meas_fetch_power(args: dict[str, Any]) -> list[TextContent]:
    """Fetch power results."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.meas_fetch_power()
    return _format_result(result.to_dict())


async def _handle_meas_fetch_spectrum(args: dict[str, Any]) -> list[TextContent]:
    """Fetch spectrum results."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.meas_fetch_spectrum()
    return _format_result(result)


async def _handle_lte_configure_cell(args: dict[str, Any]) -> list[TextContent]:
    """Configure LTE cell."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    config = CellConfig(
        band=args["band"],
        bandwidth_mhz=args["bandwidth_mhz"],
        dl_earfcn=args["dl_earfcn"],
        dl_level_dbm=args.get("dl_level_dbm", -60.0),
    )
    await cmw.lte_configure_cell(config)
    return _format_result({"status": "ok", "cell_config": config.to_dict()})


async def _handle_lte_cell_on(args: dict[str, Any]) -> list[TextContent]:
    """Turn on LTE cell."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.lte_cell_on()
    return _format_result({"status": "ok", "cell": "ON"})


async def _handle_lte_cell_off(args: dict[str, Any]) -> list[TextContent]:
    """Turn off LTE cell."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.lte_cell_off()
    return _format_result({"status": "ok", "cell": "OFF"})


async def _handle_lte_get_connection_state(args: dict[str, Any]) -> list[TextContent]:
    """Get LTE connection state."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    state = await cmw.lte_get_connection_state()
    return _format_result({"connection_state": state.strip()})


async def _handle_lte_configure_nas(args: dict[str, Any]) -> list[TextContent]:
    """Configure NAS."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    mcc = args.get("mcc", "001")
    mnc = args.get("mnc", "01")
    await cmw.lte_configure_nas(mcc, mnc)
    return _format_result({"status": "ok", "mcc": mcc, "mnc": mnc})


async def _handle_lte_configure_bearer(args: dict[str, Any]) -> list[TextContent]:
    """Configure bearer."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.lte_configure_bearer()
    return _format_result({"status": "ok", "bearer": "configured"})


async def _handle_lte_configure_cdrx(args: dict[str, Any]) -> list[TextContent]:
    """Configure C-DRX."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    enabled = args.get("enabled", False)
    await cmw.lte_configure_cdrx(enabled)
    return _format_result({"status": "ok", "cdrx": "enabled" if enabled else "disabled"})


async def _handle_lte_get_ue_info(args: dict[str, Any]) -> list[TextContent]:
    """Get UE info."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    info = await cmw.lte_get_ue_info()
    return _format_result(info)


async def _handle_lte_meas_configure(args: dict[str, Any]) -> list[TextContent]:
    """Configure LTE measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_configure()
    return _format_result(result)


async def _handle_lte_meas_trigger(args: dict[str, Any]) -> list[TextContent]:
    """Trigger LTE measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.lte_meas_trigger()
    return _format_result({"status": "ok", "measurement": "lte_meval_triggered"})


async def _handle_lte_meas_fetch_power(args: dict[str, Any]) -> list[TextContent]:
    """Fetch LTE power."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_power()
    return _format_result(result.to_dict())


async def _handle_lte_meas_fetch_evm(args: dict[str, Any]) -> list[TextContent]:
    """Fetch LTE EVM."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_evm()
    return _format_result(result.to_dict())


async def _handle_lte_meas_fetch_aclr(args: dict[str, Any]) -> list[TextContent]:
    """Fetch LTE ACLR."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_aclr()
    return _format_result(result.to_dict())


async def _handle_lte_meas_fetch_sem(args: dict[str, Any]) -> list[TextContent]:
    """Fetch LTE SEM."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_sem()
    return _format_result(result.to_dict())


async def _handle_lte_meas_fetch_frequency_error(
    args: dict[str, Any],
) -> list[TextContent]:
    """Fetch LTE frequency error."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_frequency_error()
    return _format_result(result)


async def _handle_lte_meas_fetch_all(args: dict[str, Any]) -> list[TextContent]:
    """Fetch all LTE measurements."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.lte_meas_fetch_all()
    return _format_result(result)


async def _handle_set_signal_path(args: dict[str, Any]) -> list[TextContent]:
    """Set signal path."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    scenario_str = args["scenario"]
    scenario = (
        SignalPath.STANDALONE if scenario_str == "standalone" else SignalPath.CS_PATH
    )
    await cmw.set_signal_path(scenario)
    return _format_result({"status": "ok", "signal_path": scenario_str})


async def _handle_get_signal_path(args: dict[str, Any]) -> list[TextContent]:
    """Get signal path."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    path = await cmw.get_signal_path()
    return _format_result({"signal_path": path.strip()})


async def _handle_scpi_send(args: dict[str, Any]) -> list[TextContent]:
    """Send raw SCPI command."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    command = args["command"]
    await cmw.scpi_send(command)
    return _format_result({"status": "ok", "command": command})


async def _handle_scpi_query(args: dict[str, Any]) -> list[TextContent]:
    """Send raw SCPI query."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    command = args["command"]
    response = await cmw.scpi_query(command)
    return _format_result({"command": command, "response": response})


async def _handle_reset(args: dict[str, Any]) -> list[TextContent]:
    """Reset CMW500."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.reset()
    return _format_result({"status": "ok", "action": "reset"})


async def _handle_preset(args: dict[str, Any]) -> list[TextContent]:
    """Preset CMW500."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.preset()
    return _format_result({"status": "ok", "action": "preset"})


async def _handle_list_templates(args: dict[str, Any]) -> list[TextContent]:
    """List available templates."""
    global _current_template
    templates = []
    for name, cls in _template_registry.items():
        instance = cls()
        templates.append(instance.get_summary())

    result: dict[str, Any] = {"templates": templates}
    if _current_template:
        result["current_template"] = _current_template.get_summary()
    return _format_result(result)


async def _handle_load_template(args: dict[str, Any]) -> list[TextContent]:
    """Load a template."""
    global _current_template
    template_name = args["template_name"]
    params = args.get("parameters", {})

    if template_name not in _template_registry:
        return _format_error(ValueError(f"Unknown template: {template_name}"))

    cls = _template_registry[template_name]
    _current_template = cls()

    # Apply parameter overrides
    if params:
        _current_template.parameters.update(params)

    return _format_result({
        "status": "ok",
        "template": _current_template.get_summary(),
    })


async def _handle_apply_template(args: dict[str, Any]) -> list[TextContent]:
    """Apply loaded template."""
    global _current_template
    if _current_template is None:
        return _format_error(ValueError("No template loaded. Use cmw_load_template first."))

    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await _current_template.apply(cmw)
    return _format_result({
        "status": "ok",
        "template_applied": _current_template.name,
    })


async def _handle_define_limit(args: dict[str, Any]) -> list[TextContent]:
    """Define a limit."""
    name = args["name"]
    parameter = args["parameter"]
    max_value = args.get("max_value")
    min_value = args.get("min_value")
    unit = args.get("unit", "")

    segment = LimitSegment(
        parameter=parameter,
        max_value=max_value,
        min_value=min_value,
        unit=unit,
        name=name,
    )
    limit = LimitLine(name=name, segments=[segment])
    _limit_manager.add_limit(limit)

    return _format_result({
        "status": "ok",
        "limit_defined": name,
        "parameter": parameter,
        "max_value": max_value,
        "min_value": min_value,
    })


async def _handle_check_limits(args: dict[str, Any]) -> list[TextContent]:
    """Check measurements against limits."""
    measurements = args["measurements"]
    # Convert to float dict
    float_measurements = {k: float(v) for k, v in measurements.items()}
    result = _limit_manager.get_overall_status(float_measurements)
    return _format_result(result)


async def _handle_clear_limits(args: dict[str, Any]) -> list[TextContent]:
    """Clear all limits."""
    _limit_manager.clear_limits()
    return _format_result({"status": "ok", "action": "limits_cleared"})


async def _handle_list_limits(args: dict[str, Any]) -> list[TextContent]:
    """List all limits."""
    limit_names = _limit_manager.list_limits()
    limits_detail = []
    for name in limit_names:
        limit = _limit_manager.get_limit(name)
        if limit:
            limits_detail.append(limit.to_dict())
    return _format_result({"limits": limits_detail, "count": len(limits_detail)})


async def _handle_save_state(args: dict[str, Any]) -> list[TextContent]:
    """Save CMW500 state."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    filename = Path(args["filename"]).name  # strip directory components
    notes = args.get("notes", "")

    filepath = _state_manager.state_directory / f"{filename}.json"
    if not filepath.resolve().is_relative_to(_state_manager.state_directory.resolve()):
        return _format_error(ValueError("Invalid filename"))

    state = await _state_manager.capture_state(cmw)
    state.notes = notes

    state.save(filepath)

    return _format_result({
        "status": "ok",
        "saved_to": str(filepath),
        "summary": state.get_summary(),
    })


async def _handle_load_state(args: dict[str, Any]) -> list[TextContent]:
    """Load and restore CMW500 state."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    filename = Path(args["filename"]).name  # strip directory components

    filepath = _state_manager.state_directory / f"{filename}.json"
    if not filepath.resolve().is_relative_to(_state_manager.state_directory.resolve()):
        return _format_error(ValueError("Invalid filename"))

    state = InstrumentState.load(filepath)
    await _state_manager.restore_state(cmw, state)

    return _format_result({
        "status": "ok",
        "loaded_from": str(filepath),
        "summary": state.get_summary(),
    })


async def _handle_get_full_state(args: dict[str, Any]) -> list[TextContent]:
    """Get full CMW500 state."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    state = await _state_manager.capture_state(cmw)
    return _format_result(state.to_dict())

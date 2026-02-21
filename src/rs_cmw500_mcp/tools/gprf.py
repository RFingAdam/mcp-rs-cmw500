"""GPRF generator and analyzer tools for CMW500."""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from ..models.cmw_types import ARBRepetition, MeasRepetition, SignalPath
from ..safety.validators import sanitize_scpi_param
from .registry import registry
from .shared import _format_result, _get_cmw

logger = logging.getLogger(__name__)


# =============================================================================
# Generator Handlers
# =============================================================================


async def _handle_gen_set_frequency(args: dict[str, Any]) -> CallToolResult:
    """Set generator frequency."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    freq = args["frequency_hz"]
    await cmw.gen_set_frequency(freq)
    return _format_result(
        {
            "status": "ok",
            "frequency_hz": freq,
            "frequency_mhz": freq / 1e6,
        }
    )


async def _handle_gen_set_level(args: dict[str, Any]) -> CallToolResult:
    """Set generator level."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    level = args["level_dbm"]
    await cmw.gen_set_level(level)
    return _format_result({"status": "ok", "level_dbm": level})


async def _handle_gen_output_on(args: dict[str, Any]) -> CallToolResult:
    """Enable generator output."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.gen_output_on()
    return _format_result({"status": "ok", "generator_output": "ON"})


async def _handle_gen_output_off(args: dict[str, Any]) -> CallToolResult:
    """Disable generator output."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.gen_output_off()
    return _format_result({"status": "ok", "generator_output": "OFF"})


async def _handle_gen_load_arb(args: dict[str, Any]) -> CallToolResult:
    """Load ARB file."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    file_path = sanitize_scpi_param(args["file_path"])
    await cmw.gen_load_arb(file_path)
    return _format_result({"status": "ok", "arb_file": file_path})


async def _handle_gen_configure_arb(args: dict[str, Any]) -> CallToolResult:
    """Configure ARB playback."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    rep = args.get("repetition", "continuous")
    arb_rep = ARBRepetition.CONTINUOUS if rep == "continuous" else ARBRepetition.SINGLE
    await cmw.gen_configure_arb(arb_rep)
    return _format_result({"status": "ok", "repetition": rep})


# =============================================================================
# Analyzer Handlers
# =============================================================================


async def _handle_meas_configure_power(args: dict[str, Any]) -> CallToolResult:
    """Configure power measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    rep_str = args.get("repetition", "singleshot")
    rep = MeasRepetition.SINGLESHOT if rep_str == "singleshot" else MeasRepetition.CONTINUOUS
    await cmw.meas_configure_power(
        statistic_count=args.get("statistic_count", 10),
        meas_length_s=args.get("meas_length_s", 0.001),
        repetition=rep,
    )
    return _format_result({"status": "ok", "measurement": "power_configured"})


async def _handle_meas_configure_spectrum(args: dict[str, Any]) -> CallToolResult:
    """Configure spectrum measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.meas_configure_spectrum(
        center_freq_hz=args.get("center_freq_hz"),
        span_hz=args.get("span_hz", 100e6),
        rbw_hz=args.get("rbw_hz", 100e3),
        detector=args.get("detector", "RMS"),
    )
    return _format_result(result)


async def _handle_meas_set_frequency(args: dict[str, Any]) -> CallToolResult:
    """Set analyzer frequency."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    freq = args["frequency_hz"]
    await cmw.meas_set_frequency(freq)
    return _format_result(
        {
            "status": "ok",
            "frequency_hz": freq,
            "frequency_mhz": freq / 1e6,
        }
    )


async def _handle_meas_set_expected_power(args: dict[str, Any]) -> CallToolResult:
    """Set expected power."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    power = args["power_dbm"]
    await cmw.meas_set_expected_power(power)
    return _format_result({"status": "ok", "expected_power_dbm": power})


async def _handle_meas_trigger(args: dict[str, Any]) -> CallToolResult:
    """Trigger power measurement."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.meas_trigger_power()
    return _format_result({"status": "ok", "measurement": "triggered"})


async def _handle_meas_fetch_power(args: dict[str, Any]) -> CallToolResult:
    """Fetch power results."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.meas_fetch_power()
    return _format_result(result.to_dict())


async def _handle_meas_fetch_spectrum(args: dict[str, Any]) -> CallToolResult:
    """Fetch spectrum results."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    result = await cmw.meas_fetch_spectrum()
    return _format_result(result)


# =============================================================================
# Signal Path Handlers
# =============================================================================


async def _handle_set_signal_path(args: dict[str, Any]) -> CallToolResult:
    """Set signal path."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    scenario_str = args["scenario"]
    scenario = SignalPath.STANDALONE if scenario_str == "standalone" else SignalPath.CS_PATH
    await cmw.set_signal_path(scenario)
    return _format_result({"status": "ok", "signal_path": scenario_str})


async def _handle_get_signal_path(args: dict[str, Any]) -> CallToolResult:
    """Get signal path."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    path = await cmw.get_signal_path()
    return _format_result({"signal_path": path.strip()})


# =============================================================================
# Registration
# =============================================================================

# Generator tools
registry.register(
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
    _handle_gen_set_frequency,
)

registry.register(
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
    _handle_gen_set_level,
)

registry.register(
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
    _handle_gen_output_on,
)

registry.register(
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
    _handle_gen_output_off,
)

registry.register(
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
    _handle_gen_load_arb,
)

registry.register(
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
    _handle_gen_configure_arb,
)

# Analyzer tools
registry.register(
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
    _handle_meas_configure_power,
)

registry.register(
    Tool(
        name="cmw_meas_configure_spectrum",
        description="Configure GPRF spectrum measurement (center freq, span, RBW, detector)",
        inputSchema={
            "type": "object",
            "properties": {
                "center_freq_hz": {
                    "type": "number",
                    "description": "Center frequency in Hz (uses current if omitted)",
                },
                "span_hz": {
                    "type": "number",
                    "description": "Frequency span in Hz (default: 100 MHz)",
                    "default": 100e6,
                },
                "rbw_hz": {
                    "type": "number",
                    "description": "Resolution bandwidth in Hz (default: 100 kHz)",
                    "default": 100e3,
                },
                "detector": {
                    "type": "string",
                    "description": "Detector type",
                    "enum": ["RMS", "PEAK"],
                    "default": "RMS",
                },
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        },
    ),
    _handle_meas_configure_spectrum,
)

registry.register(
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
    _handle_meas_set_frequency,
)

registry.register(
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
    _handle_meas_set_expected_power,
)

registry.register(
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
    _handle_meas_trigger,
)

registry.register(
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
    _handle_meas_fetch_power,
)

registry.register(
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
    _handle_meas_fetch_spectrum,
)

# Signal path tools
registry.register(
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
    _handle_set_signal_path,
)

registry.register(
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
    _handle_get_signal_path,
)

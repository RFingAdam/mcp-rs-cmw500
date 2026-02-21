"""State management tools for CMW500."""

import logging
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult, Tool

from ..safety.validators import validate_safe_path
from ..state import InstrumentState
from .registry import registry
from .shared import _format_result, _get_cmw, _state_manager

logger = logging.getLogger(__name__)


# =============================================================================
# Handlers
# =============================================================================


async def _handle_save_state(args: dict[str, Any]) -> CallToolResult:
    """Save CMW500 state."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    filename = Path(args["filename"]).name  # strip directory components
    notes = args.get("notes", "")

    filepath = validate_safe_path(f"{filename}.json", _state_manager.state_directory)

    state = await _state_manager.capture_state(cmw)
    state.notes = notes

    state.save(filepath)

    return _format_result(
        {
            "status": "ok",
            "saved_to": str(filepath),
            "summary": state.get_summary(),
        }
    )


async def _handle_load_state(args: dict[str, Any]) -> CallToolResult:
    """Load and restore CMW500 state."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    filename = Path(args["filename"]).name  # strip directory components

    filepath = validate_safe_path(f"{filename}.json", _state_manager.state_directory)

    state = InstrumentState.load(filepath)
    await _state_manager.restore_state(cmw, state)

    return _format_result(
        {
            "status": "ok",
            "loaded_from": str(filepath),
            "summary": state.get_summary(),
        }
    )


async def _handle_get_full_state(args: dict[str, Any]) -> CallToolResult:
    """Get full CMW500 state."""
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    state = await _state_manager.capture_state(cmw)
    return _format_result(state.to_dict())


# =============================================================================
# Registration
# =============================================================================

registry.register(
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
    _handle_save_state,
)

registry.register(
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
    _handle_load_state,
)

registry.register(
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
    _handle_get_full_state,
)

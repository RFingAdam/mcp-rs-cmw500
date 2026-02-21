"""Template management tools for CMW500."""

import logging
from typing import Any

from mcp.types import CallToolResult, Tool

from . import shared as _shared
from .registry import registry
from .shared import (
    _format_error,
    _format_result,
    _get_cmw,
    _template_lock,
    _template_registry,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Handlers
# =============================================================================


async def _handle_list_templates(args: dict[str, Any]) -> CallToolResult:
    """List available templates."""
    templates = []
    for name, cls in _template_registry.items():
        instance = cls()
        templates.append(instance.get_summary())

    async with _template_lock:
        result: dict[str, Any] = {"templates": templates}
        if _shared._current_template:
            result["current_template"] = _shared._current_template.get_summary()
    return _format_result(result)


async def _handle_load_template(args: dict[str, Any]) -> CallToolResult:
    """Load a template."""
    template_name = args["template_name"]
    params = args.get("parameters", {})

    if template_name not in _template_registry:
        return _format_error(ValueError(f"Unknown template: {template_name}"))

    cls = _template_registry[template_name]

    async with _template_lock:
        _shared._current_template = cls()

        # Apply parameter overrides
        if params:
            _shared._current_template.parameters.update(params)

        return _format_result(
            {
                "status": "ok",
                "template": _shared._current_template.get_summary(),
            }
        )


async def _handle_apply_template(args: dict[str, Any]) -> CallToolResult:
    """Apply loaded template."""
    async with _template_lock:
        if _shared._current_template is None:
            return _format_error(ValueError("No template loaded. Use cmw_load_template first."))

        cmw = await _get_cmw(args.get("host"), args.get("port"))
        await _shared._current_template.apply(cmw)
        return _format_result(
            {
                "status": "ok",
                "template_applied": _shared._current_template.name,
            }
        )


# =============================================================================
# Registration
# =============================================================================

registry.register(
    Tool(
        name="cmw_list_templates",
        description="List available measurement templates",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    _handle_list_templates,
)

registry.register(
    Tool(
        name="cmw_load_template",
        description="Load a measurement template by name",
        inputSchema={
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Template name",
                    "enum": list(_template_registry.keys()),
                },
                "parameters": {
                    "type": "object",
                    "description": "Optional parameter overrides",
                },
            },
            "required": ["template_name"],
        },
    ),
    _handle_load_template,
)

registry.register(
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
    _handle_apply_template,
)

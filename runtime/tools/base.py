"""Tool base utilities — schema validation for DomeKit tools."""

from __future__ import annotations

from typing import Any

import jsonschema

from contracts.tool_sdk import BaseTool


def validate_args(tool: BaseTool, args: dict[str, Any]) -> None:
    """Validate *args* against the tool's input_schema.

    Raises ``jsonschema.ValidationError`` on invalid input.
    """
    schema = tool.definition().input_schema
    jsonschema.validate(instance=args, schema=schema)

"""Built-in read_file tool — read files within allowed prefixes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contracts.tool_sdk import BaseTool, ToolContext, ToolDefinition, ToolOutput

_DEFAULT_MAX_BYTES = 1_048_576  # 1 MB


class ReadFileTool(BaseTool):
    """Read a file's content, respecting policy allow-read prefixes."""

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description="Read the contents of a file on the local filesystem.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path to read."},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            permissions=["fs:read"],
        )

    async def run(self, ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
        file_path = args["path"]
        call_id = getattr(ctx, "request_id", "")

        allowed_prefixes: list[str] = ctx.manifest_data_paths.get("fs_allow_read", [])
        resolved = Path(file_path).resolve()

        # Path traversal prevention: resolved path must start with an allowed prefix
        if not any(
            str(resolved).startswith(str(Path(prefix).resolve()))
            for prefix in allowed_prefixes
        ):
            return ToolOutput(
                call_id=call_id,
                tool_name="read_file",
                error=f"Path not allowed: {file_path}",
                success=False,
            )

        max_bytes: int = ctx.manifest_data_paths.get("max_bytes", _DEFAULT_MAX_BYTES)

        try:
            content = resolved.read_bytes()[:max_bytes].decode(errors="replace")
        except Exception as exc:
            return ToolOutput(
                call_id=call_id,
                tool_name="read_file",
                error=str(exc),
                success=False,
            )

        return ToolOutput(
            call_id=call_id,
            tool_name="read_file",
            result=content,
        )

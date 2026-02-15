"""Built-in write_file tool — write files within allowed prefixes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contracts.tool_sdk import BaseTool, ToolContext, ToolDefinition, ToolOutput

_DEFAULT_MAX_BYTES = 1_048_576  # 1 MB


class WriteFileTool(BaseTool):
    """Write content to a file, respecting policy allow-write prefixes."""

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_file",
            description="Write content to a file on the local filesystem.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path to write."},
                    "content": {"type": "string", "description": "Content to write to the file."},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            permissions=["fs:write"],
        )

    async def run(self, ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
        file_path = args["path"]
        content = args["content"]
        call_id = getattr(ctx, "request_id", "")

        allowed_prefixes: list[str] = ctx.manifest_data_paths.get("fs_allow_write", [])
        resolved = Path(file_path).resolve()

        # Path traversal prevention
        if not any(
            str(resolved).startswith(str(Path(prefix).resolve()))
            for prefix in allowed_prefixes
        ):
            return ToolOutput(
                call_id=call_id,
                tool_name="write_file",
                error=f"Path not allowed: {file_path}",
                success=False,
            )

        max_bytes: int = ctx.manifest_data_paths.get("max_bytes", _DEFAULT_MAX_BYTES)
        if len(content.encode()) > max_bytes:
            return ToolOutput(
                call_id=call_id,
                tool_name="write_file",
                error=f"Content exceeds max_bytes limit ({max_bytes})",
                success=False,
            )

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content)
        except Exception as exc:
            return ToolOutput(
                call_id=call_id,
                tool_name="write_file",
                error=str(exc),
                success=False,
            )

        return ToolOutput(
            call_id=call_id,
            tool_name="write_file",
            result={"status": "ok", "bytes_written": len(content.encode())},
        )

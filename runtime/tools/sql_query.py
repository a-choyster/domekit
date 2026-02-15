"""Built-in sql_query tool — read-only SQLite queries."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from contracts.tool_sdk import BaseTool, ToolContext, ToolDefinition, ToolOutput

_DEFAULT_MAX_ROWS = 100


class SqlQueryTool(BaseTool):
    """Execute a read-only SQL query against an allowed SQLite database."""

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="sql_query",
            description="Run a read-only SQL query against a local SQLite database.",
            input_schema={
                "type": "object",
                "properties": {
                    "db_path": {"type": "string", "description": "Path to the SQLite database file."},
                    "query": {"type": "string", "description": "SQL query to execute (read-only)."},
                },
                "required": ["db_path", "query"],
                "additionalProperties": False,
            },
            permissions=["data:sqlite"],
        )

    async def run(self, ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
        db_path = args["db_path"]
        query = args["query"]
        call_id = getattr(ctx, "request_id", "")

        # Validate db_path against allowed SQLite paths from manifest
        allowed: list[str] = ctx.manifest_data_paths.get("sqlite_allow", [])
        resolved = str(Path(db_path).resolve())
        if not any(resolved == str(Path(a).resolve()) for a in allowed):
            return ToolOutput(
                call_id=call_id,
                tool_name="sql_query",
                error=f"Database path not allowed: {db_path}",
                success=False,
            )

        max_rows: int = ctx.manifest_data_paths.get("max_rows", _DEFAULT_MAX_ROWS)

        try:
            conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
            try:
                cursor = conn.execute(query)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                all_rows = cursor.fetchmany(max_rows + 1)
                truncated = len(all_rows) > max_rows
                rows = [list(r) for r in all_rows[:max_rows]]
            finally:
                conn.close()
        except Exception as exc:
            return ToolOutput(
                call_id=call_id,
                tool_name="sql_query",
                error=str(exc),
                success=False,
            )

        return ToolOutput(
            call_id=call_id,
            tool_name="sql_query",
            result={"columns": columns, "rows": rows, "truncated": truncated},
        )

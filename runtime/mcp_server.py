"""DomeKit MCP server — exposes policy-checked tools over stdio transport."""

from __future__ import annotations

import json
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

from contracts.audit import AuditEntry, AuditEvent
from contracts.policy import PolicyVerdict
from contracts.tool_sdk import ToolContext, ToolInput

from runtime.mcp_helpers import DomeKitComponents, init_domekit

# ── Initialisation ────────────────────────────────────────────────────

_components: DomeKitComponents | None = None

mcp = FastMCP("domekit")


def _get_components() -> DomeKitComponents:
    """Return initialised components, lazily loading on first access."""
    global _components  # noqa: PLW0603
    if _components is None:
        _components = init_domekit()
    return _components


def _build_tool_context(components: DomeKitComponents, request_id: str) -> ToolContext:
    """Build a ToolContext from the manifest, mirroring ToolRouter logic."""
    m = components.manifest
    sql_config = m.tools.get("sql_query")
    read_config = m.tools.get("read_file")
    return ToolContext(
        request_id=request_id,
        app_name=m.app.name,
        policy_mode=m.runtime.policy_mode.value,
        manifest_data_paths={
            "sqlite_allow": m.policy.data.sqlite.allow,
            "fs_allow_read": m.policy.data.filesystem.allow_read,
            "fs_allow_write": m.policy.data.filesystem.allow_write,
            "max_rows": sql_config.max_rows if sql_config else 100,
            "max_bytes": read_config.max_bytes if read_config else 65536,
            "vector_allow": m.policy.data.vector.allow,
            "vector_allow_write": m.policy.data.vector.allow_write,
            "vector_backend": m.vector_db.backend,
            "default_top_k": m.vector_db.default_top_k,
        },
    )


async def _run_tool(tool_name: str, args: dict[str, Any]) -> str:
    """Policy-check, execute, and audit-log a single tool call.

    Returns a JSON string with the result or a human-readable denial.
    """
    c = _get_components()
    request_id = str(uuid.uuid4())
    call_id = str(uuid.uuid4())

    # Policy check
    tool_input = ToolInput(tool_name=tool_name, arguments=args, call_id=call_id)
    decision = c.policy.check_tool(tool_input)

    if decision.verdict == PolicyVerdict.DENY:
        c.logger.log(AuditEntry(
            request_id=request_id,
            event=AuditEvent.POLICY_BLOCK,
            app=c.manifest.app.name,
            policy_mode=c.manifest.runtime.policy_mode.value,
            detail={
                "tool": tool_name,
                "rule": decision.rule,
                "reason": decision.reason,
                "transport": "mcp",
            },
        ))
        return f"Policy denied: {decision.reason}"

    # Audit: tool.call
    c.logger.log(AuditEntry(
        request_id=request_id,
        event=AuditEvent.TOOL_CALL,
        app=c.manifest.app.name,
        policy_mode=c.manifest.runtime.policy_mode.value,
        detail={"tool": tool_name, "arguments": args, "transport": "mcp"},
    ))

    # Execute
    ctx = _build_tool_context(c, request_id)
    try:
        tool = c.registry.get(tool_name)
        output = await tool.run(ctx, args)
    except KeyError:
        result = json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as exc:
        result = json.dumps({"error": str(exc)})
    else:
        if output.error:
            result = json.dumps({"error": output.error, "success": False})
        else:
            result = json.dumps({"result": output.result, "success": True})

    # Audit: tool.result
    c.logger.log(AuditEntry(
        request_id=request_id,
        event=AuditEvent.TOOL_RESULT,
        app=c.manifest.app.name,
        policy_mode=c.manifest.runtime.policy_mode.value,
        detail={"tool": tool_name, "call_id": call_id, "transport": "mcp"},
    ))

    return result


# ── MCP tool wrappers ─────────────────────────────────────────────────


@mcp.tool()
async def sql_query(db_path: str, query: str) -> str:
    """Execute a read-only SQL query against an allowed SQLite database."""
    return await _run_tool("sql_query", {"db_path": db_path, "query": query})


@mcp.tool()
async def read_file(path: str) -> str:
    """Read the contents of a file on the local filesystem."""
    return await _run_tool("read_file", {"path": path})


@mcp.tool()
async def write_file(path: str, content: str) -> str:
    """Write content to a file on the local filesystem."""
    return await _run_tool("write_file", {"path": path, "content": content})


@mcp.tool()
async def vector_search(
    collection: str,
    query: str = "",
    top_k: int = 5,
) -> str:
    """Search a local vector database collection by semantic similarity."""
    args: dict[str, Any] = {"collection": collection}
    if query:
        args["query"] = query
    args["top_k"] = top_k
    return await _run_tool("vector_search", args)


@mcp.tool()
async def vector_manage(
    collection: str,
    operation: str,
    documents: list[dict[str, Any]] | None = None,
    ids: list[str] | None = None,
) -> str:
    """Insert, update, or delete documents in a local vector database collection."""
    args: dict[str, Any] = {"collection": collection, "operation": operation}
    if documents is not None:
        args["documents"] = documents
    if ids is not None:
        args["ids"] = ids
    return await _run_tool("vector_manage", args)


# ── Entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")

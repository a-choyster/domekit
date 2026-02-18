# DomeKit MCP Server

DomeKit exposes its 5 policy-checked tools as an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server. Any MCP-compatible client — Claude Desktop, Cursor, Windsurf, OpenClaw, and others — can use DomeKit's tools with full policy enforcement and audit logging.

## Why Use the MCP Server?

The HTTP API (`/v1/chat/completions`) works well when the LLM routes tool calls through DomeKit's proxy. But clients that execute tools locally bypass DomeKit entirely. The MCP server solves this by running tools inside DomeKit regardless of the client.

**Claude Desktop / Claude Code** — Configure DomeKit MCP in your settings. When Claude calls `sql_query`, the query runs through DomeKit's policy engine, is checked against `domekit.yaml`, and logged to `audit.jsonl`.

**Cursor / Windsurf / IDE agents** — Add DomeKit MCP to your IDE agent config. The agent can query databases and read files, but only within the paths allowed by your manifest.

**Multi-agent orchestration** — Platforms like OpenClaw or AutoGen connect to DomeKit MCP as a tool server. Each agent's tool calls go through policy checks, and the audit log provides a complete trace.

**Local RAG with guardrails** — Any MCP client can search your local vector embeddings, but only in collections allowed by the manifest.

## Available Tools

| Tool | Description |
|------|-------------|
| `sql_query` | Execute a read-only SQL query against an allowed SQLite database |
| `read_file` | Read the contents of a file on the local filesystem |
| `write_file` | Write content to a file on the local filesystem |
| `vector_search` | Search a local vector database collection by semantic similarity |
| `vector_manage` | Insert, update, or delete documents in a vector database collection |

All tools are subject to the same policy rules defined in your `domekit.yaml` manifest.

## Setup

### Prerequisites

```bash
pip install -e ".[dev]"
# or just: pip install mcp>=1.0
```

### Running the MCP Server

```bash
# Using the CLI
python cli/domekit.py mcp domekit.yaml

# Or directly
DOMEKIT_MANIFEST=./domekit.yaml python -m runtime.mcp_server
```

The server uses **stdio transport** (standard for MCP).

### Claude Desktop

Add this to your `claude_desktop_config.json` (typically at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "domekit": {
      "command": "python",
      "args": ["-m", "runtime.mcp_server"],
      "cwd": "/path/to/domekit",
      "env": {
        "DOMEKIT_MANIFEST": "/path/to/your/domekit.yaml"
      }
    }
  }
}
```

Restart Claude Desktop. DomeKit's 5 tools will appear in the tools list.

### Claude Code

In your `.claude/settings.json` or project-level config:

```json
{
  "mcpServers": {
    "domekit": {
      "command": "python",
      "args": ["cli/domekit.py", "mcp", "/path/to/domekit.yaml"],
      "cwd": "/path/to/domekit"
    }
  }
}
```

### Cursor

Add to your Cursor MCP settings (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "domekit": {
      "command": "python",
      "args": ["-m", "runtime.mcp_server"],
      "cwd": "/path/to/domekit",
      "env": {
        "DOMEKIT_MANIFEST": "/path/to/your/domekit.yaml"
      }
    }
  }
}
```

### Generic MCP Client

Any MCP client that supports stdio transport can connect. The server reads the manifest from the `DOMEKIT_MANIFEST` environment variable (defaults to `./domekit.yaml`).

## How It Works

The MCP server is a thin adapter layer. It reuses the same components as the HTTP server:

- **Same manifest** — reads `DOMEKIT_MANIFEST` or `./domekit.yaml`
- **Same policy engine** — `DomeKitPolicyEngine` checks every tool call
- **Same audit log** — writes to the same `audit.jsonl` (HTTP and MCP calls appear in one unified log)
- **Same tool implementations** — `SqlQueryTool`, `ReadFileTool`, etc.

When a tool call is policy-blocked, the MCP server returns a readable text message (not an exception) so the LLM can explain to the user why access was denied. Audit entries from MCP calls include `"transport": "mcp"` in their detail to distinguish them from HTTP calls.

## Manifest Reference

The MCP server respects all manifest fields. Key sections:

```yaml
policy:
  tools:
    allow: [sql_query, read_file]     # Which tools MCP clients can call
  data:
    sqlite:
      allow: ["data/my.db"]           # Allowed SQLite database paths
    filesystem:
      allow_read: ["./data/*"]        # Allowed file read patterns
      allow_write: ["./output/*"]     # Allowed file write patterns
    vector:
      allow: ["my-collection"]        # Vector collections allowed for search
      allow_write: ["my-collection"]  # Collections allowed for insert/update/delete
```

See [docs/manifest-reference.md](manifest-reference.md) for the full reference.

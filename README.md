# DomeKit

**Local-first AI runtime with enforced privacy boundaries.**

DomeKit runs AI models on your machine with manifest-driven policy enforcement. No data leaves your device — every tool call is checked against your policy and every action is audit-logged.

[![Tests](https://img.shields.io/badge/tests-89%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Observability Dashboard](#observability-dashboard)
- [Manifest Reference](#manifest-reference)
- [API Reference](#api-reference)
- [Built-in Tools](#built-in-tools)
- [CLI Usage](#cli-usage)
- [Development](#development)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

---

## Overview

DomeKit is a **privacy-first AI runtime** that brings AI capabilities to your local environment with strict policy enforcement. Unlike cloud-based AI services, DomeKit:

- ✅ **Runs entirely locally** — no API keys, no external calls
- ✅ **Enforces data boundaries** — manifest-driven allow/deny rules
- ✅ **Audits everything** — append-only JSONL logs for compliance
- ✅ **OpenAI-compatible** — drop-in replacement for OpenAI API
- ✅ **Zero trust by default** — explicit permission for every operation

### Use Cases

- **Healthcare & HIPAA compliance** — process patient data locally with audit trails
- **Financial services** — analyze sensitive data without cloud exposure
- **Legal & confidential work** — document analysis with zero data leakage
- **Development & testing** — build AI features without external dependencies
- **Research & academia** — reproducible AI workflows with local models

---

## Key Features

### 🔒 Manifest-Driven Security

Every app declares its permissions in a `domekit.yaml` file:

```yaml
policy:
  network:
    outbound: deny              # No external network access
  tools:
    allow: [sql_query]          # Only SQL queries allowed
  data:
    sqlite:
      allow: ["data/my.db"]     # Specific database only
```

DomeKit validates every tool call against this manifest **before execution**.

### 📝 Append-Only Audit Log

Every action is logged in tamper-evident JSONL format:

```json
{"ts":"2026-02-13T21:27:31Z","request_id":"abc123","event":"request.start","app":"health-poc"}
{"ts":"2026-02-13T21:27:33Z","request_id":"abc123","event":"tool.call","detail":{"tool":"sql_query"}}
{"ts":"2026-02-13T21:27:33Z","request_id":"abc123","event":"tool.result","detail":{"tool":"sql_query"}}
{"ts":"2026-02-13T21:27:36Z","request_id":"abc123","event":"request.end","detail":{"tools_used":["sql_query"]}}
```

Perfect for **compliance**, **debugging**, and **security audits**.

### 🛠️ Built-in Tools with Safety

DomeKit ships with three secure built-in tools:

| Tool | Purpose | Safety Features |
|------|---------|----------------|
| `sql_query` | Read-only SQLite queries | Path validation, read-only mode, row limits |
| `read_file` | File reading | Path traversal prevention, prefix validation, size limits |
| `write_file` | File writing | Path traversal prevention, prefix validation, size limits |

All tools enforce manifest boundaries and prevent common attacks (path traversal, SQL injection, etc.).

### 🔄 Model Adapter System

DomeKit supports multiple local model backends:

- **Ollama** — run Llama, Mistral, Qwen, Gemma, and more
- **Prompt-based tool calling** — automatic fallback for models without native tool support (e.g. gemma3, gemma2). Tool definitions are injected into the system prompt and tool calls are parsed from model output.
- **Native tool calling** — used automatically when the model supports it (e.g. Qwen, Llama 3.1+)
- Extensible — add your own adapters for other backends

---

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Client Application                                         │
│  (your code, CLI, web app, etc.)                            │
└────────────────┬────────────────────────────────────────────┘
                 │ HTTP POST /v1/chat/completions
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  DomeKit Runtime Server (FastAPI)                           │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ ToolRouter — orchestrates model ↔ tool loop       │     │
│  │                                                    │     │
│  │  1. Send messages to model                        │     │
│  │  2. Model returns tool_calls?                     │     │
│  │     ├─ Yes → check policy → execute → loop        │     │
│  │     └─ No  → return response                      │     │
│  │                                                    │     │
│  │  Components:                                       │     │
│  │  ┌──────────────┐  ┌──────────────┐               │     │
│  │  │ OllamaAdapter│  │ PolicyEngine │               │     │
│  │  │ (to model)   │  │ (check rules)│               │     │
│  │  └──────────────┘  └──────────────┘               │     │
│  │  ┌──────────────┐  ┌──────────────┐               │     │
│  │  │ ToolRegistry │  │ AuditLogger  │               │     │
│  │  │ (execute)    │  │ (log events) │               │     │
│  │  └──────────────┘  └──────────────┘               │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Ollama (local model server)                                │
│  llama3.1, mistral, qwen, etc.                              │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow Diagram

```
User Query
    ↓
┌───────────────────────────────────────────────────────────┐
│ 1. Load manifest & initialize components                 │
│    - Parse domekit.yaml                                   │
│    - Load policy rules                                    │
│    - Initialize tool registry                             │
│    - Open audit log                                       │
└───────────────┬───────────────────────────────────────────┘
                ↓
┌───────────────────────────────────────────────────────────┐
│ 2. Log request.start event                                │
└───────────────┬───────────────────────────────────────────┘
                ↓
┌───────────────────────────────────────────────────────────┐
│ 3. Send messages to model (via OllamaAdapter)             │
└───────────────┬───────────────────────────────────────────┘
                ↓
        ┌───────┴───────┐
        │ Model returns  │
        └───────┬───────┘
                ↓
    ┌───────────────────────┐
    │ tool_calls present?   │
    └───────┬───────────────┘
            │
    ┌───────┴────────┐
    │                │
   YES              NO
    │                │
    ↓                ↓
┌────────────┐  ┌────────────┐
│ For each   │  │ Return     │
│ tool_call: │  │ response   │
│            │  └────────────┘
│ ┌────────┐ │
│ │ Policy │ │
│ │ check  │ │
│ └───┬────┘ │
│     │      │
│  ┌──┴───┐  │
│  │Allow?│  │
│  └──┬───┘  │
│     │      │
│  ┌──┴────────────┐
│  │               │
│ YES             NO
│  │               │
│  ↓               ↓
│ Execute      Log policy.block
│ tool         Return error
│  │               │
│  ↓               │
│ Log tool.call    │
│ Log tool.result  │
│  │               │
│  └───────┬───────┘
│          ↓
│    Append result
│    to messages
│          │
└──────────┴─────────┐
                     ↓
            Loop (max 5 iterations)
                     ↓
┌───────────────────────────────────────────────────────────┐
│ 4. Log request.end event                                  │
└───────────────┬───────────────────────────────────────────┘
                ↓
┌───────────────────────────────────────────────────────────┐
│ 5. Return ChatResponse with trace metadata                │
│    - request_id                                            │
│    - tools_used                                            │
│    - tables_queried                                        │
│    - policy_mode                                           │
└───────────────────────────────────────────────────────────┘
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        DomeKit Runtime                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ runtime/app.py — FastAPI Application                      │ │
│  │                                                            │ │
│  │  Endpoints:                                                │ │
│  │  • POST /v1/chat/completions                              │ │
│  │  • GET  /v1/domekit/health                                │ │
│  │  • GET  /v1/domekit/audit/{request_id}                    │ │
│  └────────────────────────┬──────────────────────────────────┘ │
│                           │                                    │
│  ┌────────────────────────▼──────────────────────────────────┐ │
│  │ runtime/tool_router.py — Tool Calling Loop                │ │
│  │                                                            │ │
│  │  • Manages conversation state                             │ │
│  │  • Coordinates model ↔ tool interactions                  │ │
│  │  • Enforces MAX_ITERATIONS limit                          │ │
│  │  • Generates trace metadata                               │ │
│  └─┬────────────┬───────────────┬───────────────┬────────────┘ │
│    │            │               │               │              │
│  ┌─▼────────┐ ┌─▼───────────┐ ┌─▼─────────┐  ┌─▼──────────┐  │
│  │ Ollama   │ │ Policy      │ │ Tool      │  │ Audit      │  │
│  │ Adapter  │ │ Engine      │ │ Registry  │  │ Logger     │  │
│  └──────────┘ └─────────────┘ └───────────┘  └────────────┘  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                      Shared Contracts                           │
│  (contracts/*.py — source of truth for all interfaces)         │
└─────────────────────────────────────────────────────────────────┘
```

### Policy Enforcement Flow

```
Tool Call Request
       ↓
┌──────────────────────────────────────┐
│ PolicyEngine.check_tool()            │
│                                      │
│ 1. Check tool name against           │
│    policy.tools.allow list           │
│                                      │
│ 2. If developer mode:                │
│    → ALLOW (skip checks)             │
│                                      │
│ 3. If local_only mode:               │
│    → Tool in allow list? ALLOW       │
│    → Otherwise? DENY                 │
└────────────┬─────────────────────────┘
             ↓
      ┌──────────────┐
      │ Result:      │
      │ ALLOW / DENY │
      └──────┬───────┘
             ↓
    ┌────────┴─────────┐
    │                  │
  ALLOW              DENY
    │                  │
    ↓                  ↓
Execute tool      Log policy.block
Log tool.call     Return error msg
Log tool.result   to model
```

---

## Installation

### Prerequisites

- **Python 3.11+**
- **Ollama** installed and running ([ollama.ai](https://ollama.ai))
- A pulled model (e.g., `ollama pull llama3.1:8b`)

### Install DomeKit

```bash
# Clone the repository
git clone https://github.com/a-choyster/domekit.git
cd domekit

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### Verify Installation

```bash
# Run tests
pytest tests/ -v

# Check Ollama is running
curl http://localhost:11434/api/tags

# Validate the example manifest
python cli/domekit.py validate apps/health-poc/domekit.yaml
```

---

## Quick Start

### 30-Minute Tutorial

#### 1. Generate Sample Health Data

```bash
python apps/health-poc/ingest/sample_data.py
python apps/health-poc/ingest/ingest.py
```

This creates `apps/health-poc/data/health.db` with 90 days of synthetic activity and health metrics.

#### 2. Review the Manifest

```bash
cat apps/health-poc/domekit.yaml
```

Key sections:
- `policy.tools.allow: [sql_query, read_file]` — only these tools are permitted
- `policy.data.sqlite.allow` — only the health.db database is accessible
- `policy.network.outbound: deny` — no external network access

#### 3. Start the Runtime

```bash
python cli/domekit.py run apps/health-poc/domekit.yaml
```

The server starts on `http://127.0.0.1:8080`.

#### 4. Ask Questions About Your Data

In another terminal:

```bash
python apps/health-poc/client/health.py ask "How many total activities are in my database?"
```

Sample output:

```
There are 79 activities in the database.

---
  request_id:     89cc5c7c-329e-43f5-a373-51dd6611928a
  tools_used:     ['sql_query']
  tables_queried: []
  policy_mode:    local_only
  model:          llama3.1:8b
```

Try more questions:

```bash
python apps/health-poc/client/health.py ask "What's my average resting heart rate?"
python apps/health-poc/client/health.py ask "Show my activities from this week"
python apps/health-poc/client/health.py ask "How are my sleep patterns?"
```

#### 5. Inspect the Audit Log

```bash
# Show last 20 audit entries
python cli/domekit.py logs apps/health-poc/data/audit.jsonl

# Filter by request ID
python cli/domekit.py logs apps/health-poc/data/audit.jsonl -r 89cc5c7c

# Show only policy.block events
python cli/domekit.py logs apps/health-poc/data/audit.jsonl -e policy.block

# Raw JSON output
python cli/domekit.py logs apps/health-poc/data/audit.jsonl --json
```

---

## Observability Dashboard

DomeKit includes a built-in observability dashboard served directly by the runtime at `/dashboard`. No build step, no external dependencies — vanilla HTML/CSS/JS with canvas-based charts.

### Accessing the Dashboard

Start the runtime and open your browser:

```bash
python cli/domekit.py run apps/health-poc/domekit.yaml
# Dashboard: http://localhost:8080/dashboard
```

### Views

| View | Route | Purpose |
|------|-------|---------|
| **Logs** | `#/logs` | Filterable audit log table with live tail (SSE), request timeline drill-down |
| **Health** | `#/health` | Runtime/Ollama/model status cards, uptime, manifest summary |
| **Security** | `#/security` | Policy block timeline, data leakage alerts (path traversal, SQL injection, burst denials) |
| **Metrics** | `#/metrics` | Request throughput, tool usage breakdown, latency percentiles (p50/p95/p99), error rates |

### Features

- **Live tail** — toggle real-time log streaming via Server-Sent Events
- **Request drill-down** — click any request ID to see a full event timeline
- **Security heuristics** — automatic detection of path traversal, SQL injection patterns, burst denials, and repeated tool blocking
- **Dark/light mode** — toggle with the Theme button in the sidebar
- **Auto-refresh** — Health and Security views poll for updates automatically
- **Responsive** — works on desktop and tablet viewports

---

## Manifest Reference

The `domekit.yaml` file defines all permissions and configuration for your app.

### Full Example

```yaml
app:
  name: my-app
  version: "1.0.0"

runtime:
  base_url: "http://127.0.0.1:8080"
  policy_mode: local_only  # or: developer

policy:
  network:
    outbound: deny  # deny | allow
    allow_domains:
      - localhost
      - 127.0.0.1

  tools:
    allow:
      - sql_query
      - read_file
      - write_file

  data:
    sqlite:
      allow:
        - "data/my.db"
        - "data/analytics.db"
    filesystem:
      allow_read:
        - "data/"
        - "config/"
      allow_write:
        - "output/"
        - "logs/"

models:
  backend: ollama
  default: llama3.1:8b
  map:
    default:
      id: llama3.1:8b
      context_window: 8192
    fast:
      id: llama3.2
      context_window: 2048

tools:
  sql_query:
    type: builtin
    read_only: true
    max_rows: 100
  read_file:
    type: builtin
    max_bytes: 1048576  # 1MB
  write_file:
    type: builtin
    max_bytes: 1048576

audit:
  path: "audit.jsonl"
  redact_prompt: false
  redact_tool_outputs: false
```

### Policy Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `local_only` | Strict enforcement of all allow lists | Production, compliance |
| `developer` | Relaxed rules, allows all tools/data/network | Development, testing |

⚠️ **Never use `developer` mode in production.**

### Path Patterns

Filesystem paths support glob patterns:

```yaml
filesystem:
  allow_read:
    - "data/*.csv"       # All CSVs in data/
    - "config/**/*.json" # All JSONs recursively
    - "/tmp/safe-*"      # Prefix match
```

SQLite paths must be exact (no globs).

---

## API Reference

### POST /v1/chat/completions

OpenAI-compatible chat completions endpoint.

**Request:**

```json
{
  "model": "default",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the capital of France?"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "sql_query",
        "description": "Run SQL query",
        "parameters": {
          "type": "object",
          "properties": {
            "db_path": {"type": "string"},
            "query": {"type": "string"}
          },
          "required": ["db_path", "query"]
        }
      }
    }
  ]
}
```

**Response:**

```json
{
  "id": "89cc5c7c-329e-43f5-a373-51dd6611928a",
  "object": "chat.completion",
  "model": "llama3.1:8b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "There are 79 activities."
      },
      "finish_reason": "stop"
    }
  ],
  "trace": {
    "request_id": "89cc5c7c-329e-43f5-a373-51dd6611928a",
    "tools_used": ["sql_query"],
    "tables_queried": [],
    "policy_mode": "local_only",
    "model": "llama3.1:8b"
  }
}
```

### GET /v1/domekit/health

Extended health check endpoint with Ollama status, uptime, and manifest summary.

**Response:**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "uptime_seconds": 3600.0,
  "manifest": {
    "app": "health-poc",
    "app_version": "0.1.0",
    "policy_mode": "local_only",
    "allowed_tools": ["sql_query", "read_file"],
    "model_backend": "ollama",
    "default_model": "llama3.1:8b"
  },
  "audit_log_size_bytes": 4515,
  "audit_log_entries": 20,
  "ollama": {
    "reachable": true,
    "models": ["llama3.1:8b", "llama3.2:latest"]
  }
}
```

### GET /v1/domekit/audit/logs

Filtered, paginated audit log query.

**Query params:** `event`, `since`, `until`, `request_id`, `limit` (default 100), `offset` (default 0)

**Response:**

```json
{
  "entries": [{ "ts": "...", "request_id": "...", "event": "request.start", ... }],
  "total": 42
}
```

### GET /v1/domekit/audit/stream

SSE (Server-Sent Events) endpoint for real-time log tailing. Connect with `EventSource` to receive new audit entries as they are written.

### GET /v1/domekit/security/alerts

Heuristic-based security alerts scanned from the audit log.

**Query params:** `since`, `limit` (default 50)

**Response:**

```json
{
  "alerts": [
    {
      "type": "sql_injection",
      "severity": "critical",
      "ts": "2026-02-13T21:27:33Z",
      "request_id": "abc123",
      "message": "SQL injection pattern detected: DROP TABLE users"
    }
  ],
  "total": 1
}
```

Alert types: `path_traversal`, `sql_injection`, `burst_denial`, `repeated_denial`

### GET /v1/domekit/metrics

Aggregated observability metrics computed from the audit log.

**Query params:** `since`, `window` (bucket size in seconds, default 60)

**Response:**

```json
{
  "throughput": [{ "time": "...", "count": 5 }],
  "latency": { "p50": 2.1, "p95": 8.3, "p99": 12.0, "count": 50 },
  "tool_usage": [{ "tool": "sql_query", "count": 30 }],
  "error_rates": { "total_requests": 50, "policy_blocks": 2, "block_rate": 0.04 },
  "summary": { "total_entries": 200, "event_counts": { "request.start": 50 } }
}
```

### GET /v1/domekit/audit/{request_id}

Query audit log by request ID.

**Response:**

```json
[
  {
    "ts": "2026-02-13T21:27:31.123456Z",
    "request_id": "89cc5c7c-329e-43f5-a373-51dd6611928a",
    "event": "request.start",
    "app": "health-poc",
    "model": "llama3.1:8b",
    "policy_mode": "local_only",
    "detail": {}
  },
  {
    "ts": "2026-02-13T21:27:33.456789Z",
    "request_id": "89cc5c7c-329e-43f5-a373-51dd6611928a",
    "event": "tool.call",
    "app": "health-poc",
    "model": "llama3.1:8b",
    "policy_mode": "local_only",
    "detail": {
      "tool": "sql_query",
      "arguments": {"db_path": "...", "query": "..."}
    }
  }
]
```

---

## Built-in Tools

### sql_query

Execute read-only SQL queries against SQLite databases.

**Definition:**

```json
{
  "name": "sql_query",
  "description": "Run a read-only SQL query against a local SQLite database.",
  "parameters": {
    "type": "object",
    "properties": {
      "db_path": {
        "type": "string",
        "description": "Path to the SQLite database file."
      },
      "query": {
        "type": "string",
        "description": "SQL query to execute (read-only)."
      }
    },
    "required": ["db_path", "query"]
  }
}
```

**Safety features:**
- Opens database in read-only mode (`file:...?mode=ro`)
- Validates `db_path` against manifest allow list
- Enforces `max_rows` limit (default 100)
- Returns `{columns, rows, truncated}` structure

**Example:**

```json
{
  "tool": "sql_query",
  "arguments": {
    "db_path": "data/analytics.db",
    "query": "SELECT COUNT(*) as total FROM events WHERE date > '2026-01-01'"
  }
}
```

**Result:**

```json
{
  "columns": ["total"],
  "rows": [[1523]],
  "truncated": false
}
```

### read_file

Read file contents from allowed filesystem paths.

**Definition:**

```json
{
  "name": "read_file",
  "description": "Read the contents of a file on the local filesystem.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Absolute or relative file path to read."
      }
    },
    "required": ["path"]
  }
}
```

**Safety features:**
- Validates path against `allow_read` prefixes
- Prevents path traversal attacks (resolves path and checks prefix)
- Enforces `max_bytes` limit (default 1MB)
- Returns decoded text content

**Example:**

```json
{
  "tool": "read_file",
  "arguments": {
    "path": "config/settings.json"
  }
}
```

### write_file

Write content to files within allowed filesystem paths.

**Definition:**

```json
{
  "name": "write_file",
  "description": "Write content to a file on the local filesystem.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Absolute or relative file path to write."
      },
      "content": {
        "type": "string",
        "description": "Content to write to the file."
      }
    },
    "required": ["path", "content"]
  }
}
```

**Safety features:**
- Validates path against `allow_write` prefixes
- Prevents path traversal attacks
- Enforces `max_bytes` on content size
- Creates parent directories automatically

---

## CLI Usage

### domekit validate

Validate a manifest file.

```bash
python cli/domekit.py validate [manifest]

# Examples:
python cli/domekit.py validate domekit.yaml
python cli/domekit.py validate apps/my-app/domekit.yaml
```

**Output:**

```
Manifest OK: health-poc v0.1.0
  Policy mode:  local_only
  Model backend: ollama
  Default model: llama3.1:8b
  Allowed tools: sql_query, read_file
  Audit path:   apps/health-poc/data/audit.jsonl
```

### domekit run

Start the DomeKit runtime server.

```bash
python cli/domekit.py run [manifest] [options]

# Options:
#   --host HOST        Bind address (default: 127.0.0.1)
#   --port PORT        Port number (default: 8080)
#   --reload           Enable auto-reload on file changes

# Examples:
python cli/domekit.py run domekit.yaml
python cli/domekit.py run apps/my-app/domekit.yaml --port 9000
python cli/domekit.py run domekit.yaml --reload  # Development mode
```

### domekit logs

Query audit logs.

```bash
python cli/domekit.py logs <audit.jsonl> [options]

# Options:
#   -r, --request-id ID    Filter by request ID
#   -e, --event EVENT      Filter by event type
#   -n, --limit N          Max entries (default: 20)
#   --json                 Output raw JSON

# Examples:
python cli/domekit.py logs audit.jsonl
python cli/domekit.py logs audit.jsonl -r 89cc5c7c -n 50
python cli/domekit.py logs audit.jsonl -e policy.block
python cli/domekit.py logs audit.jsonl --json | jq '.'
```

**Event types:**
- `request.start` — New chat request begins
- `tool.call` — Tool about to be executed
- `tool.result` — Tool execution completed
- `request.end` — Chat request finished
- `policy.block` — Tool call denied by policy

---

## Development

### Project Structure

```
domekit/
├── contracts/              # Shared interfaces (source of truth)
│   ├── api.py              # OpenAI-compatible request/response
│   ├── audit.py            # Audit log interfaces
│   ├── manifest.py         # Manifest schema (Pydantic)
│   ├── policy.py           # Policy engine interface
│   └── tool_sdk.py         # Tool development interface
├── runtime/
│   ├── app.py              # FastAPI application
│   ├── tool_router.py      # Tool calling loop orchestrator
│   ├── policy.py           # Policy engine implementation
│   ├── manifest_loader.py  # YAML manifest parser
│   ├── security.py         # Security alert heuristics
│   ├── metrics.py          # Metrics aggregation
│   ├── audit/
│   │   ├── logger.py       # Append-only JSONL logger
│   │   └── query.py        # Audit query functions
│   ├── model_adapters/
│   │   └── ollama.py       # Ollama adapter (native + prompt-based tool calling)
│   └── tools/
│       ├── base.py         # Tool validation helpers
│       ├── registry.py     # Tool registry
│       ├── sql_query.py    # SQLite query tool
│       ├── read_file.py    # File reading tool
│       └── write_file.py   # File writing tool
├── dashboard/              # Observability dashboard (vanilla JS)
│   ├── index.html          # SPA shell
│   ├── css/styles.css      # Layout + dark/light themes
│   └── js/
│       ├── app.js          # Hash router + init
│       ├── api.js          # Backend fetch wrapper
│       ├── views/          # Logs, Health, Security, Metrics
│       ├── components/     # Table, Badge, Card, Chart, Timeline
│       └── lib/            # SSE manager, formatting utils
├── apps/
│   └── health-poc/         # Reference application
│       ├── domekit.yaml    # Example manifest
│       ├── client/         # CLI client
│       ├── ingest/         # Data generation scripts
│       └── data/           # Sample database
├── cli/
│   └── domekit.py          # CLI tool
├── tests/
│   ├── unit/               # Component tests
│   └── integration/        # End-to-end tests
├── scripts/
│   └── no-egress-proof.sh  # Zero-egress verification script
└── docs/                   # Documentation
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run specific test file
pytest tests/unit/test_policy.py -v

# Run with coverage
pytest tests/ --cov=runtime --cov-report=html
```

**Test Coverage:**
- 82 unit tests covering all components (including security heuristics and metrics aggregation)
- 13 integration tests covering end-to-end flows
- **89 total tests** (67 unit + 22 new for dashboard backend)

### Adding a New Tool

1. **Define the tool** (inherit from `BaseTool`):

```python
from contracts.tool_sdk import BaseTool, ToolContext, ToolDefinition, ToolOutput
from typing import Any

class MyCustomTool(BaseTool):
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="my_tool",
            description="Does something useful",
            input_schema={
                "type": "object",
                "properties": {
                    "param": {"type": "string"}
                },
                "required": ["param"]
            },
            permissions=["custom:permission"]
        )

    async def run(self, ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
        # Your implementation here
        result = f"Processed: {args['param']}"
        return ToolOutput(
            call_id=ctx.request_id,
            tool_name="my_tool",
            result=result,
        )
```

2. **Register the tool**:

```python
# In runtime/tools/registry.py
from runtime.tools.my_tool import MyCustomTool

def create_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SqlQueryTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(MyCustomTool())  # Add your tool
    return registry
```

3. **Update the manifest**:

```yaml
policy:
  tools:
    allow:
      - my_tool
```

4. **Write tests**:

```python
def test_my_custom_tool():
    tool = MyCustomTool()
    ctx = ToolContext(request_id="test", app_name="test")
    output = await tool.run(ctx, {"param": "test"})
    assert output.success
    assert "Processed: test" in output.result
```

---

## Security

### No-Egress Proof

DomeKit includes a verification script that proves zero network egress:

```bash
./scripts/no-egress-proof.sh apps/health-poc/domekit.yaml
```

This script:
1. Validates manifest blocks network (`outbound: deny`)
2. Tests tool calling loop with mocked model (no real network)
3. Verifies policy engine denies all outbound hosts
4. Confirms zero socket connections during request processing

### Security Best Practices

✅ **DO:**
- Start with `policy_mode: local_only`
- Use exact paths for SQLite databases (no globs)
- Keep `network.outbound: deny` in production
- Review audit logs regularly
- Use `max_rows` and `max_bytes` limits
- Run with least privilege (non-root user)

❌ **DON'T:**
- Use `policy_mode: developer` in production
- Allow `/` or `*` in filesystem paths
- Disable audit logging
- Run as root
- Expose the runtime to public networks

### Threat Model

| Threat | Mitigation |
|--------|------------|
| **Data exfiltration via network** | `network.outbound: deny` blocks all egress |
| **Unauthorized database access** | Manifest whitelist + path validation |
| **Path traversal attacks** | Path resolution + prefix validation |
| **SQL injection** | Read-only mode + parameterized queries |
| **Privilege escalation** | No shell execution, sandboxed tools |
| **Audit log tampering** | Append-only JSONL, file permissions |

### Compliance

DomeKit is designed to support compliance with:
- **HIPAA** — local processing, audit trails, access controls
- **GDPR** — data minimization, right to audit, local storage
- **SOC 2** — audit logging, access controls, policy enforcement
- **PCI DSS** — data isolation, audit trails, least privilege

⚠️ **Consult your compliance team** — DomeKit provides tools for compliance but doesn't guarantee it.

---

## Troubleshooting

### Model Not Calling Tools

**Symptoms:** Model returns text explanations instead of using tools.

**Solutions:**
1. DomeKit automatically falls back to prompt-based tool calling for models that don't support native tools (gemma3, gemma2). No configuration needed.
2. For best results with tool calling, use models that support native tools: Qwen 2.5, Llama 3.1+, Mistral
3. Check the system prompt guides the model to use tools
4. Verify tools are in the manifest `allow` list
5. Check audit log for `policy.block` events

```bash
python cli/domekit.py logs audit.jsonl -e policy.block
```

### Tool Execution Fails

**Symptoms:** Tool called but returns errors.

**Solutions:**
1. Check the tool has access to required resources:
   ```yaml
   policy:
     data:
       sqlite:
         allow: ["path/to/database.db"]  # Exact path
   ```
2. Verify file/database exists and is readable
3. Check audit log for error details:
   ```bash
   python cli/domekit.py logs audit.jsonl -r <request_id>
   ```

### Ollama Connection Issues

**Symptoms:** `Connection refused` or `Cannot connect to Ollama`.

**Solutions:**
1. Verify Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   ```
2. Start Ollama if needed:
   ```bash
   ollama serve
   ```
3. Check model is pulled:
   ```bash
   ollama list
   ollama pull llama3.1:8b
   ```

### Audit Log Not Created

**Symptoms:** No `audit.jsonl` file.

**Solutions:**
1. Check manifest `audit.path` is correct
2. Verify parent directory exists and is writable
3. Check runtime logs for permission errors

### Tests Failing

**Symptoms:** `pytest` shows failures.

**Solutions:**
1. Reinstall dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
2. Check Python version:
   ```bash
   python --version  # Should be 3.11+
   ```
3. Run specific failing test with verbose output:
   ```bash
   pytest tests/path/to/test.py::test_name -vv
   ```

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Code of Conduct
- Development setup
- Pull request process
- Coding standards

### Quick Start for Contributors

```bash
# Fork and clone
git clone https://github.com/a-choyster/domekit.git
cd domekit

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Make your changes, add tests, commit
git checkout -b feature/my-feature
# ... make changes ...
pytest tests/ -v
git commit -m "feat: add my feature"

# Push and create PR
git push origin feature/my-feature
```

---

## License

DomeKit is released under the [MIT License](LICENSE).

---

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [Ollama](https://ollama.ai)
- Inspired by privacy-first AI principles

---

## Support

- 📖 **Documentation:** [docs/](docs/)
- 🐛 **Bug reports:** [GitHub Issues](https://github.com/a-choyster/domekit/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/a-choyster/domekit/discussions)
- 📧 **Email:** [Open an issue](https://github.com/a-choyster/domekit/issues)

---

**Built with ❤️ for privacy-conscious AI applications.**

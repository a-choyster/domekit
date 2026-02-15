# API Reference

## POST /v1/chat/completions

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

## GET /v1/domekit/health

Extended health check with Ollama status, uptime, and manifest summary.

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

## GET /v1/domekit/audit/logs

Filtered, paginated audit log query.

**Query params:** `event`, `since`, `until`, `request_id`, `limit` (default 100), `offset` (default 0)

**Response:**

```json
{
  "entries": [{ "ts": "...", "request_id": "...", "event": "request.start" }],
  "total": 42
}
```

## GET /v1/domekit/audit/stream

SSE (Server-Sent Events) endpoint for real-time log tailing. Connect with `EventSource` to receive new audit entries as they are written.

## GET /v1/domekit/security/alerts

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

## GET /v1/domekit/metrics

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

## GET /v1/domekit/audit/{request_id}

Query audit log entries for a specific request.

**Response:**

```json
[
  {
    "ts": "2026-02-13T21:27:31.123456Z",
    "request_id": "89cc5c7c",
    "event": "request.start",
    "app": "health-poc",
    "model": "llama3.1:8b",
    "policy_mode": "local_only",
    "detail": {}
  },
  {
    "ts": "2026-02-13T21:27:33.456789Z",
    "request_id": "89cc5c7c",
    "event": "tool.call",
    "detail": {
      "tool": "sql_query",
      "arguments": {"db_path": "...", "query": "..."}
    }
  }
]
```

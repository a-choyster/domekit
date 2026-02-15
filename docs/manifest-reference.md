# Manifest Reference

The `domekit.yaml` file defines all permissions and configuration for your app.

## Full Example

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

## Policy Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `local_only` | Strict enforcement of all allow lists | Production, compliance |
| `developer` | Relaxed rules, allows all tools/data/network | Development, testing |

**Never use `developer` mode in production.**

## Path Patterns

Filesystem paths support glob patterns:

```yaml
filesystem:
  allow_read:
    - "data/*.csv"       # All CSVs in data/
    - "config/**/*.json" # All JSONs recursively
    - "/tmp/safe-*"      # Prefix match
```

SQLite paths must be exact (no globs).

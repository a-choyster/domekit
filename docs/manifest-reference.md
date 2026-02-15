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
      - vector_search
      - vector_manage

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
    vector:
      allow:
        - "my-collection"
        - "docs-*"
      allow_write:
        - "my-collection"

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
  vector_search:
    type: builtin
  vector_manage:
    type: builtin

embedding:
  backend: ollama
  model: nomic-embed-text

vector_db:
  backend: chroma
  default_top_k: 10

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

## Embedding Configuration

Configure local embeddings for vector search. DomeKit uses Ollama to generate embeddings on your machine.

```yaml
embedding:
  backend: ollama                  # Embedding provider (currently: ollama)
  model: nomic-embed-text          # Ollama embedding model to use
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `backend` | string | `"ollama"` | Embedding provider |
| `model` | string | `"nomic-embed-text"` | Model name (must be pulled in Ollama) |

The embedding adapter is used by `vector_search` (auto-embeds text queries) and `vector_manage` (auto-embeds documents on insert/update).

## Vector DB Configuration

Configure the vector database backend for semantic search.

```yaml
vector_db:
  backend: chroma                  # "chroma" or "lance"
  default_top_k: 10               # Default result limit for searches
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `backend` | string | `"chroma"` | Vector DB backend — `chroma` (ChromaDB) or `lance` (LanceDB) |
| `default_top_k` | integer | `10` | Default number of results returned by `vector_search` |

Both backends persist data to disk. ChromaDB uses its own storage format; LanceDB uses the Lance columnar format.

## Vector Data Policy

Control which vector collections the agent can access. Defined under `policy.data.vector`.

```yaml
policy:
  data:
    vector:
      allow:                       # Collections the agent can search (read)
        - "health-*"               # Glob patterns supported
        - "docs"
      allow_write:                 # Collections the agent can modify
        - "health-activities"      # Must be explicitly listed
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `allow` | list[string] | `[]` | Collection paths/patterns allowed for `vector_search` |
| `allow_write` | list[string] | `[]` | Collection paths/patterns allowed for `vector_manage` |

Read access does not grant write access — they are separate allow-lists. Glob patterns (e.g., `health-*`) are supported for both.

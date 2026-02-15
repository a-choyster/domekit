# DomeKit

**Local-first AI runtime with enforced privacy boundaries.**

DomeKit runs AI models on your machine with manifest-driven policy enforcement. No data leaves your device — every tool call is checked against your policy and every action is audit-logged.

[![Tests](https://img.shields.io/badge/tests-129%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

---

## Why DomeKit?

You run AI models locally with Ollama. But there's no control over what those models can access, no record of what they did, and no way to enforce boundaries.

DomeKit adds the missing layer:

- **Manifest-driven permissions** — a YAML file declares exactly which tools, databases, and files your AI can touch
- **Policy enforcement** — every tool call is checked against your manifest before execution
- **Audit logging** — append-only JSONL log of every request, tool call, and policy decision
- **Zero egress** — provably no network access with `outbound: deny`
- **OpenAI-compatible API** — drop-in replacement, works with any client

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/a-choyster/domekit.git
cd domekit
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Generate sample data
python apps/health-poc/ingest/sample_data.py
python apps/health-poc/ingest/ingest.py

# Start the runtime
python cli/domekit.py run apps/health-poc/domekit.yaml
```

In another terminal:

```bash
python apps/health-poc/client/health.py ask "How many activities are in my database?"
```

Open the dashboard at `http://localhost:8080/dashboard` to see logs, metrics, and security alerts.

---

## How It Works

Everything is controlled by a `domekit.yaml` manifest:

```yaml
app:
  name: my-app

policy:
  network:
    outbound: deny                    # No external network access
  tools:
    allow: [sql_query, read_file,
            vector_search]            # Only these tools permitted
  data:
    sqlite:
      allow: ["data/my.db"]          # Only this database accessible
    vector:
      allow: ["my-collection"]        # Vector collections the agent can search
      allow_write: []                 # No vector writes

models:
  backend: ollama
  default: llama3.1:8b

embedding:
  backend: ollama
  model: nomic-embed-text             # Local embeddings via Ollama

vector_db:
  backend: chroma                     # ChromaDB or LanceDB
  default_top_k: 10

audit:
  path: "audit.jsonl"
```

DomeKit validates every tool call against this manifest, logs every action, and blocks anything not explicitly allowed. Supports SQLite, ChromaDB, and LanceDB as data backends — all policy-controlled.

```
Client → DomeKit Runtime → Policy Check → Tool Execution → Audit Log
                ↕                              ↕
         Ollama (local model)     SQLite · ChromaDB · LanceDB
```

---

## Built-in Tools

| Tool | Purpose | Safety |
|------|---------|--------|
| `sql_query` | Read-only SQLite queries | Path validation, read-only mode, row limits |
| `read_file` | File reading | Path traversal prevention, size limits |
| `write_file` | File writing | Path traversal prevention, size limits |
| `vector_search` | Semantic similarity search over vector collections | Collection allow-list, top-k limits |
| `vector_manage` | Insert, update, delete documents in vector collections | Separate write allow-list, policy-checked |

---

## Framework Examples

DomeKit exposes an OpenAI-compatible API — any framework that talks to OpenAI works out of the box. Point it at `localhost:8080/v1` instead of OpenAI and DomeKit handles permissions and audit logging transparently.

| Framework | Example Repo |
|-----------|-------------|
| LangChain | [domekit-langchain-example](https://github.com/a-choyster/domekit-langchain-example) |
| CrewAI | [domekit-crewai-example](https://github.com/a-choyster/domekit-crewai-example) |
| LlamaIndex | [domekit-llamaindex-example](https://github.com/a-choyster/domekit-llamaindex-example) |

### Demo Apps

Included in this repo under `apps/`:

| App | What it demonstrates |
|-----|---------------------|
| `apps/health-poc/` | Health data query agent with SQL + vector search |
| `apps/file-analyst/` | File analysis agent restricted to a specific directory |
| `apps/research-agent/` | Research agent with SQL + vector search + zero network access |

---

## Dashboard

Built-in observability dashboard at `/dashboard` — no build step, no dependencies.

| View | What it shows |
|------|---------------|
| **Logs** | Filterable audit log with live tail (SSE), request drill-down |
| **Health** | Runtime/Ollama status, uptime, manifest summary |
| **Security** | Policy blocks, path traversal and SQL injection alerts |
| **Metrics** | Throughput, latency percentiles, tool usage, error rates |

---

## CLI

```bash
# Validate a manifest
python cli/domekit.py validate apps/health-poc/domekit.yaml

# Start the runtime
python cli/domekit.py run apps/health-poc/domekit.yaml

# Query audit logs
python cli/domekit.py logs audit.jsonl -e policy.block
python cli/domekit.py logs audit.jsonl -r <request_id>
```

---

## Documentation

| Topic | Link |
|-------|------|
| Architecture & diagrams | [docs/architecture.md](docs/architecture.md) |
| Manifest reference | [docs/manifest-reference.md](docs/manifest-reference.md) |
| API reference | [docs/api-reference.md](docs/api-reference.md) |
| Built-in tools | [docs/built-in-tools.md](docs/built-in-tools.md) |
| Security & threat model | [docs/security.md](docs/security.md) |
| Development & contributing | [docs/development.md](docs/development.md) |
| Troubleshooting | [docs/troubleshooting.md](docs/troubleshooting.md) |

---

## Contributing

```bash
git clone https://github.com/a-choyster/domekit.git
cd domekit
pip install -e ".[dev]"
pytest tests/ -v
```

129 tests (unit + integration). See [docs/development.md](docs/development.md) for details.

---

## License

MIT — see [LICENSE](LICENSE).

---

**Links:** [GitHub](https://github.com/a-choyster/domekit) | [Issues](https://github.com/a-choyster/domekit/issues) | [Discussions](https://github.com/a-choyster/domekit/discussions)

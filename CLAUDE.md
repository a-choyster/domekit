# DomeKit — Project Context

## What This Is
DomeKit is a local-first AI runtime with enforced privacy boundaries.
Phase 0 builds: runtime server, policy engine, tool SDK, audit logging,
and a health PoC reference app.

## Architecture
- FastAPI server exposing OpenAI-compatible API on localhost:8080
- Manifest-driven policy enforcement (domekit.yaml)
- Tool SDK with built-in tools: sql_query, read_file, write_file
- Append-only JSONL audit logging
- Ollama as the local model backend

## Shared Contracts
All components import from `contracts/`. These are the source of truth
for interfaces. Do NOT redefine types — import them.

## Tech Stack
- Python 3.11+
- FastAPI + Uvicorn
- Pydantic v2
- SQLite (stdlib sqlite3)
- httpx (for Ollama adapter)
- PyYAML
- jsonschema

## Rules
- NO cloud inference — everything runs locally
- NO external dependencies beyond what's in requirements.txt
- ALL tool calls must go through the policy engine
- ALL actions must be audit logged
- Import shared types from contracts/ — do not duplicate
- Type hints on all public functions
- Each component must have unit tests

## File Ownership (to avoid conflicts)
- runtime/app.py, runtime/tool_router.py, runtime/model_adapters/ → Runtime agent
- runtime/policy.py, runtime/manifest_loader.py, runtime/audit/ → Policy agent
- runtime/tools/ → Tools agent
- apps/health-poc/ → Health PoC agent
- tests/, cli/, docker-compose.yml, README.md → Integrator agent

# Architecture

## High-Level Overview

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

## Request Flow

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

## Component Diagram

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

## Policy Enforcement Flow

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

## Project Structure

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
│   │   └── ollama.py       # Ollama adapter (native + prompt-based)
│   └── tools/
│       ├── base.py         # Tool validation helpers
│       ├── registry.py     # Tool registry
│       ├── sql_query.py    # SQLite query tool
│       ├── read_file.py    # File reading tool
│       └── write_file.py   # File writing tool
├── dashboard/              # Observability dashboard (vanilla JS)
│   ├── index.html
│   ├── css/styles.css
│   └── js/
├── apps/
│   └── health-poc/         # Reference application
├── cli/
│   └── domekit.py          # CLI tool
├── tests/
│   ├── unit/
│   └── integration/
├── scripts/
│   └── no-egress-proof.sh  # Zero-egress verification
└── docs/
```

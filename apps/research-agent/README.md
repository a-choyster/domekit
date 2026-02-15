# Research Agent — Zero Network Access Demo

A DomeKit demo that gives an AI agent full access to sensitive R&D data
(SQL database, project briefs, vector search) while enforcing **zero
outbound network access**. Data stays on-device, period.

## What this proves

The agent can query a SQLite database of research projects and findings
(some marked confidential), read markdown project briefs, and perform
semantic vector search — but the DomeKit policy engine blocks every
outbound network call. Sensitive research data physically cannot leave
the machine.

## Security model

| Capability | Allowed |
|---|---|
| `sql_query` on `research.db` | Yes (read-only) |
| `read_file` in `data/` | Yes |
| `vector_search` on `research-notes` | Yes |
| Outbound network (any host/port) | **Denied** |
| File writes | **Denied** |

Every tool invocation is appended to `audit.jsonl` for accountability.

## Quick start

```bash
# 1. Generate sample data
python apps/research-agent/setup_data.py

# 2. Start the DomeKit runtime with this app's policy
domekit run apps/research-agent

# 3. Ask questions (in another terminal)
python apps/research-agent/client/ask.py "What are our active projects?"
python apps/research-agent/client/ask.py "Show confidential findings for Project Aurora"
python apps/research-agent/client/ask.py "Which project has the largest budget?"
```

## Audit log

Every query the agent makes is recorded in `apps/research-agent/audit.jsonl`.
Each entry includes the tool called, parameters, timestamp, and policy
verdict so you can reconstruct exactly what the agent accessed.

# file-analyst

A DomeKit demo app that shows an AI agent with strict filesystem boundaries. The agent can only read files from a single directory (`data/reports/`) and query a SQLite index — nothing else.

## What this demonstrates

- **Path traversal prevention**: the policy restricts `read_file` to `apps/file-analyst/data/reports/`. Any attempt to read outside that directory (e.g., `/etc/passwd`, `../../runtime/app.py`) is blocked by the policy engine before it reaches the filesystem.
- **Outbound network denied**: the agent cannot make any network calls.
- **Write access denied**: `allow_write` is empty, so the agent is read-only.
- **Audit trail**: every tool call (allowed or denied) is logged to `audit.jsonl`.

## Quick start

```bash
# 1. Generate sample reports and the SQLite index
python apps/file-analyst/setup_data.py

# 2. Start DomeKit with this app's manifest
domekit run --app apps/file-analyst

# 3. Ask questions
python apps/file-analyst/client/ask.py "Summarize the Q4 2025 revenue report"
python apps/file-analyst/client/ask.py "What security issues were found in the January audit?"
python apps/file-analyst/client/ask.py "How many people are we hiring in 2026?"
```

## What happens on policy violation

If the agent tries to read a file outside the allowed path, DomeKit's policy engine rejects the tool call and returns an error to the model. The denied attempt is recorded in `audit.jsonl` with the reason. The agent never gains access to the file contents.

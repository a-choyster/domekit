# Built-in Tools

## sql_query

Execute read-only SQL queries against SQLite databases.

**Definition:**

```json
{
  "name": "sql_query",
  "description": "Run a read-only SQL query against a local SQLite database.",
  "parameters": {
    "type": "object",
    "properties": {
      "db_path": { "type": "string", "description": "Path to the SQLite database file." },
      "query": { "type": "string", "description": "SQL query to execute (read-only)." }
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

## read_file

Read file contents from allowed filesystem paths.

**Definition:**

```json
{
  "name": "read_file",
  "description": "Read the contents of a file on the local filesystem.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": { "type": "string", "description": "Absolute or relative file path to read." }
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

## write_file

Write content to files within allowed filesystem paths.

**Definition:**

```json
{
  "name": "write_file",
  "description": "Write content to a file on the local filesystem.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": { "type": "string", "description": "Absolute or relative file path to write." },
      "content": { "type": "string", "description": "Content to write to the file." }
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

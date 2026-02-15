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

## vector_search

Search a local vector database collection by semantic similarity.

**Definition:**

```json
{
  "name": "vector_search",
  "description": "Search a local vector database collection by semantic similarity.",
  "parameters": {
    "type": "object",
    "properties": {
      "collection": { "type": "string", "description": "Path to the vector collection." },
      "query": { "type": "string", "description": "Text to search for (auto-embedded)." },
      "query_vector": {
        "type": "array",
        "items": { "type": "number" },
        "description": "Raw embedding vector (alternative to text query)."
      },
      "top_k": { "type": "integer", "default": 10, "description": "Number of results to return." },
      "filters": { "type": "object", "description": "Metadata filters." }
    },
    "required": ["collection"]
  }
}
```

**Safety features:**
- Validates `collection` against `policy.data.vector.allow` list (supports glob patterns)
- Requires either `query` (auto-embedded via Ollama) or `query_vector` — not both omitted
- Enforces `top_k` limit from args or manifest `default_top_k`
- Returns normalized similarity scores (0–1)

**Example:**

```json
{
  "tool": "vector_search",
  "arguments": {
    "collection": "health-activities",
    "query": "morning running sessions",
    "top_k": 5
  }
}
```

**Result:**

```json
{
  "results": [
    {
      "id": "act-0042",
      "text": "30 minute morning run, 5km",
      "metadata": { "date": "2026-01-15", "type": "running" },
      "score": 0.87
    }
  ]
}
```

## vector_manage

Insert, update, or delete documents in a local vector database collection.

**Definition:**

```json
{
  "name": "vector_manage",
  "description": "Insert, update, or delete documents in a local vector database collection.",
  "parameters": {
    "type": "object",
    "properties": {
      "collection": { "type": "string", "description": "Path to the vector collection." },
      "operation": {
        "type": "string",
        "enum": ["insert", "update", "delete"],
        "description": "Operation to perform."
      },
      "documents": {
        "type": "array",
        "items": { "type": "object" },
        "description": "Documents with text and optional metadata."
      },
      "ids": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Document IDs (for update/delete)."
      }
    },
    "required": ["collection", "operation"]
  }
}
```

**Safety features:**
- Validates `collection` against `policy.data.vector.allow_write` list (supports glob patterns)
- Separate write allow-list — read access does not grant write access
- Auto-embeds document text via the configured embedding adapter
- Skips embedding for documents with pre-computed embeddings

**Example (insert):**

```json
{
  "tool": "vector_manage",
  "arguments": {
    "collection": "health-activities",
    "operation": "insert",
    "documents": [
      { "text": "Evening yoga session, 45 minutes", "metadata": { "type": "yoga" } }
    ]
  }
}
```

**Example (delete):**

```json
{
  "tool": "vector_manage",
  "arguments": {
    "collection": "health-activities",
    "operation": "delete",
    "ids": ["act-0042"]
  }
}
```

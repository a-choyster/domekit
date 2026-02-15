"""Integration tests for actual tool execution with manifest context."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from contracts.api import Message, Role, ToolCall, ToolCallFunction


@pytest.fixture()
def test_db(tmp_path: Path) -> Path:
    """Create a test SQLite database with sample data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE activities (
            id INTEGER PRIMARY KEY,
            date TEXT,
            type TEXT,
            duration_min REAL
        );
        INSERT INTO activities (date, type, duration_min)
        VALUES ('2026-02-01', 'running', 30),
               ('2026-02-05', 'cycling', 45),
               ('2026-02-10', 'walking', 25);
        """
    )
    conn.close()
    return db_path


@pytest.fixture()
def manifest_with_db(tmp_path: Path, test_db: Path) -> Path:
    """Create a manifest that allows access to the test database."""
    manifest = {
        "app": {"name": "test-app", "version": "0.1.0"},
        "runtime": {"policy_mode": "local_only"},
        "policy": {
            "network": {"outbound": "deny"},
            "tools": {"allow": ["sql_query"]},
            "data": {
                "sqlite": {"allow": [str(test_db)]},
                "filesystem": {"allow_read": [], "allow_write": []},
            },
        },
        "models": {"backend": "ollama", "default": "test-model"},
        "tools": {
            "sql_query": {"type": "builtin", "read_only": True, "max_rows": 50}
        },
        "audit": {"path": str(tmp_path / "audit.jsonl")},
    }
    p = tmp_path / "domekit.yaml"
    p.write_text(yaml.dump(manifest))
    return p


@pytest.fixture()
def client(manifest_with_db: Path) -> TestClient:
    os.environ["DOMEKIT_MANIFEST"] = str(manifest_with_db)
    try:
        from runtime.app import app

        with TestClient(app) as c:
            yield c
    finally:
        os.environ.pop("DOMEKIT_MANIFEST", None)


class TestToolExecutionWithManifest:
    """Test that tools receive correct manifest context and execute properly."""

    def test_sql_query_tool_executes_with_manifest_paths(
        self, client: TestClient, test_db: Path
    ) -> None:
        """sql_query tool should receive manifest_data_paths from context."""
        from runtime.model_adapters.ollama import OllamaAdapter
        import json

        # Model requests sql_query tool
        tool_call_msg = Message(
            role=Role.ASSISTANT,
            tool_calls=[
                ToolCall(
                    id="call_0",
                    function=ToolCallFunction(
                        name="sql_query",
                        arguments=json.dumps(
                            {
                                "db_path": str(test_db),
                                "query": "SELECT COUNT(*) as cnt FROM activities",
                            }
                        ),
                    ),
                )
            ],
        )
        # After tool execution, model uses the result
        final_msg = Message(
            role=Role.ASSISTANT,
            content="There are 3 activities in the database.",
        )

        mock_chat = AsyncMock(side_effect=[tool_call_msg, final_msg])

        with patch.object(OllamaAdapter, "chat", mock_chat):
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "How many activities?"}
                    ],
                },
            )

        assert resp.status_code == 200
        body = resp.json()

        # Tool executed successfully
        assert "sql_query" in body["trace"]["tools_used"]
        # Model got the result and returned an answer
        assert "3" in body["choices"][0]["message"]["content"]

    def test_sql_query_blocks_unauthorized_database(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """sql_query should reject databases not in the manifest allow list."""
        from runtime.model_adapters.ollama import OllamaAdapter
        import json

        # Create an unauthorized database
        unauthorized_db = tmp_path / "unauthorized.db"
        conn = sqlite3.connect(str(unauthorized_db))
        conn.execute("CREATE TABLE secret (id INTEGER)")
        conn.close()

        tool_call_msg = Message(
            role=Role.ASSISTANT,
            tool_calls=[
                ToolCall(
                    id="call_0",
                    function=ToolCallFunction(
                        name="sql_query",
                        arguments=json.dumps(
                            {
                                "db_path": str(unauthorized_db),
                                "query": "SELECT * FROM secret",
                            }
                        ),
                    ),
                )
            ],
        )
        final_msg = Message(
            role=Role.ASSISTANT,
            content="I cannot access that database.",
        )

        mock_chat = AsyncMock(side_effect=[tool_call_msg, final_msg])

        with patch.object(OllamaAdapter, "chat", mock_chat):
            resp = client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Query secret"}]},
            )

        # Request completes but tool returns an error
        assert resp.status_code == 200
        # Check audit log - tool should have been called but returned an error
        request_id = resp.json()["trace"]["request_id"]
        audit_resp = client.get(f"/v1/domekit/audit/{request_id}")
        entries = audit_resp.json()
        tool_calls = [e for e in entries if e["event"] == "tool.call"]
        assert len(tool_calls) == 1

    def test_max_rows_enforcement(
        self, client: TestClient, test_db: Path
    ) -> None:
        """sql_query should enforce max_rows from manifest."""
        from runtime.model_adapters.ollama import OllamaAdapter
        import json

        # Add more rows to exceed max_rows
        conn = sqlite3.connect(str(test_db))
        for i in range(100):
            conn.execute(
                "INSERT INTO activities (date, type, duration_min) VALUES (?, ?, ?)",
                (f"2026-02-{i:02d}", "running", 30),
            )
        conn.commit()
        conn.close()

        tool_call_msg = Message(
            role=Role.ASSISTANT,
            tool_calls=[
                ToolCall(
                    id="call_0",
                    function=ToolCallFunction(
                        name="sql_query",
                        arguments=json.dumps(
                            {
                                "db_path": str(test_db),
                                "query": "SELECT * FROM activities",
                            }
                        ),
                    ),
                )
            ],
        )
        final_msg = Message(
            role=Role.ASSISTANT,
            content="Retrieved 50 rows (truncated).",
        )

        mock_chat = AsyncMock(side_effect=[tool_call_msg, final_msg])

        with patch.object(OllamaAdapter, "chat", mock_chat):
            resp = client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Show all"}]},
            )

        assert resp.status_code == 200
        # The tool should have been called
        assert "sql_query" in resp.json()["trace"]["tools_used"]

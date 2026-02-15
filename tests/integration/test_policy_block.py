"""Integration test: verify policy blocking works end-to-end."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from contracts.api import Message, Role, ToolCall, ToolCallFunction


@pytest.fixture()
def health_db(tmp_path: Path) -> Path:
    """Create a minimal health.db for testing."""
    import sqlite3

    db_path = tmp_path / "health.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE activities (id INTEGER PRIMARY KEY, date TEXT, type TEXT)"
    )
    conn.execute("INSERT INTO activities VALUES (1, '2025-12-01', 'running')")
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def blocked_manifest_file(tmp_path: Path, health_db: Path) -> Path:
    """Manifest with sql_query REMOVED from allowed tools."""
    manifest = {
        "app": {"name": "test-blocked", "version": "0.1.0"},
        "runtime": {"policy_mode": "local_only"},
        "policy": {
            "network": {"outbound": "deny"},
            "tools": {"allow": ["read_file"]},  # sql_query NOT listed
            "data": {
                "sqlite": {"allow": [str(health_db)]},
                "filesystem": {"allow_read": [str(tmp_path)]},
            },
        },
        "models": {"backend": "ollama", "default": "test-model"},
        "audit": {"path": str(tmp_path / "audit.jsonl")},
    }
    p = tmp_path / "domekit.yaml"
    p.write_text(yaml.dump(manifest))
    return p


@pytest.fixture()
def client(blocked_manifest_file: Path) -> TestClient:
    os.environ["DOMEKIT_MANIFEST"] = str(blocked_manifest_file)
    try:
        from runtime.app import app

        with TestClient(app) as c:
            yield c
    finally:
        os.environ.pop("DOMEKIT_MANIFEST", None)


class TestPolicyBlock:
    def test_sql_query_blocked_when_not_allowed(
        self, client: TestClient, health_db: Path
    ) -> None:
        """When sql_query is not in the allow list, it should be blocked by policy."""
        from runtime.model_adapters.ollama import OllamaAdapter

        # Model tries to call sql_query
        tool_call_msg = Message(
            role=Role.ASSISTANT,
            tool_calls=[
                ToolCall(
                    id="call_0",
                    function=ToolCallFunction(
                        name="sql_query",
                        arguments=json.dumps(
                            {"db_path": str(health_db), "query": "SELECT 1"}
                        ),
                    ),
                )
            ],
        )
        # After getting the denial, model responds with text
        final_msg = Message(
            role=Role.ASSISTANT,
            content="I'm sorry, I can't run SQL queries with current permissions.",
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
        request_id = body["trace"]["request_id"]

        # Verify policy.block was logged
        audit_resp = client.get(f"/v1/domekit/audit/{request_id}")
        assert audit_resp.status_code == 200
        entries = audit_resp.json()
        events = [e["event"] for e in entries]
        assert "policy.block" in events

        # The block entry should mention sql_query
        block_entries = [e for e in entries if e["event"] == "policy.block"]
        assert len(block_entries) == 1
        assert block_entries[0]["detail"]["tool"] == "sql_query"

        # sql_query should NOT appear in tool.call events (it was blocked)
        tool_call_events = [e for e in entries if e["event"] == "tool.call"]
        tool_names = [e["detail"].get("tool") for e in tool_call_events]
        assert "sql_query" not in tool_names

    def test_allowed_tool_still_works(
        self, client: TestClient, health_db: Path, tmp_path: Path
    ) -> None:
        """read_file is still allowed even though sql_query is blocked."""
        from runtime.model_adapters.ollama import OllamaAdapter

        # Create a test file to read
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello from test")

        tool_call_msg = Message(
            role=Role.ASSISTANT,
            tool_calls=[
                ToolCall(
                    id="call_0",
                    function=ToolCallFunction(
                        name="read_file",
                        arguments=json.dumps({"path": str(test_file)}),
                    ),
                )
            ],
        )
        final_msg = Message(
            role=Role.ASSISTANT, content="The file says: hello from test"
        )

        mock_chat = AsyncMock(side_effect=[tool_call_msg, final_msg])

        with patch.object(OllamaAdapter, "chat", mock_chat):
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "Read test.txt"}],
                },
            )

        assert resp.status_code == 200
        request_id = resp.json()["trace"]["request_id"]

        audit_resp = client.get(f"/v1/domekit/audit/{request_id}")
        entries = audit_resp.json()
        events = [e["event"] for e in entries]

        # No policy blocks
        assert "policy.block" not in events
        # read_file was called
        assert "tool.call" in events

"""End-to-end integration tests for DomeKit runtime with the health PoC manifest."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from contracts.api import Message, Role, ToolCall, ToolCallFunction
from contracts.audit import AuditEvent

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HEALTH_MANIFEST = PROJECT_ROOT / "apps" / "health-poc" / "domekit.yaml"


@pytest.fixture()
def health_db(tmp_path: Path) -> Path:
    """Create a small health.db for testing."""
    import sqlite3

    db_path = tmp_path / "health.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, type TEXT, duration_min REAL,
            distance_km REAL, avg_hr INTEGER, calories INTEGER
        );
        CREATE TABLE daily_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, steps INTEGER, resting_hr INTEGER,
            sleep_hours REAL, active_minutes INTEGER, stress_score INTEGER
        );
        INSERT INTO activities (date, type, duration_min, distance_km, avg_hr, calories)
        VALUES ('2025-12-01', 'running', 30, 5.0, 150, 350),
               ('2025-12-02', 'cycling', 45, 15.0, 130, 400),
               ('2025-12-03', 'walking', 25, 2.0, 95, 120);
        INSERT INTO daily_metrics (date, steps, resting_hr, sleep_hours, active_minutes, stress_score)
        VALUES ('2025-12-01', 8000, 62, 7.5, 45, 3),
               ('2025-12-02', 10500, 60, 8.0, 60, 2),
               ('2025-12-03', 6000, 63, 6.5, 30, 5);
        """
    )
    conn.close()
    return db_path


@pytest.fixture()
def manifest_file(tmp_path: Path, health_db: Path) -> Path:
    """Write a test manifest pointing at the tmp health.db."""
    import yaml

    audit_path = str(tmp_path / "audit.jsonl")
    manifest = {
        "app": {"name": "health-poc", "version": "0.1.0"},
        "runtime": {"policy_mode": "local_only"},
        "policy": {
            "network": {"outbound": "deny"},
            "tools": {"allow": ["sql_query", "read_file"]},
            "data": {
                "sqlite": {"allow": [str(health_db)]},
                "filesystem": {"allow_read": [str(tmp_path)]},
            },
        },
        "models": {"backend": "ollama", "default": "test-model"},
        "tools": {
            "sql_query": {"type": "builtin", "read_only": True, "max_rows": 50},
            "read_file": {"type": "builtin", "max_bytes": 65536},
        },
        "audit": {"path": audit_path},
    }
    p = tmp_path / "domekit.yaml"
    p.write_text(yaml.dump(manifest))
    return p


@pytest.fixture()
def client(manifest_file: Path) -> TestClient:
    """Create a TestClient with the test manifest loaded."""
    os.environ["DOMEKIT_MANIFEST"] = str(manifest_file)
    try:
        from runtime.app import app

        with TestClient(app) as c:
            yield c
    finally:
        os.environ.pop("DOMEKIT_MANIFEST", None)


def _mock_model_with_tool_call(
    db_path: str,
) -> AsyncMock:
    """Return a mock that first requests sql_query, then returns a summary."""
    tool_call_msg = Message(
        role=Role.ASSISTANT,
        tool_calls=[
            ToolCall(
                id="call_0",
                function=ToolCallFunction(
                    name="sql_query",
                    arguments=json.dumps(
                        {
                            "db_path": db_path,
                            "query": "SELECT COUNT(*) AS cnt FROM activities",
                        }
                    ),
                ),
            )
        ],
    )
    final_msg = Message(
        role=Role.ASSISTANT,
        content="You have 3 activities recorded.",
    )
    return AsyncMock(side_effect=[tool_call_msg, final_msg])


class TestE2E:
    def test_chat_completion_with_tool_call(
        self, client: TestClient, health_db: Path
    ) -> None:
        """Full flow: user asks question → model calls sql_query → returns answer."""
        from runtime.model_adapters.ollama import OllamaAdapter

        mock_chat = _mock_model_with_tool_call(str(health_db))

        with patch.object(OllamaAdapter, "chat", mock_chat):
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "How many activities do I have?"}
                    ],
                },
            )

        assert resp.status_code == 200
        body = resp.json()

        # Model returned the final answer
        assert "3 activities" in body["choices"][0]["message"]["content"]

        # Trace shows sql_query was used
        trace = body["trace"]
        assert "sql_query" in trace["tools_used"]
        assert trace["policy_mode"] == "local_only"

    def test_audit_trail_sequence(
        self, client: TestClient, health_db: Path, tmp_path: Path
    ) -> None:
        """Verify the audit log contains the correct event sequence."""
        from runtime.model_adapters.ollama import OllamaAdapter

        mock_chat = _mock_model_with_tool_call(str(health_db))

        with patch.object(OllamaAdapter, "chat", mock_chat):
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "Count my activities"}
                    ],
                },
            )

        request_id = resp.json()["trace"]["request_id"]

        # Query audit log via the API
        audit_resp = client.get(f"/v1/domekit/audit/{request_id}")
        assert audit_resp.status_code == 200
        entries = audit_resp.json()
        events = [e["event"] for e in entries]

        # Verify the expected sequence
        assert events[0] == "request.start"
        assert "tool.call" in events
        assert "tool.result" in events
        assert events[-1] == "request.end"

    def test_no_policy_block_for_allowed_operations(
        self, client: TestClient, health_db: Path
    ) -> None:
        """Allowed tools should not produce policy.block events."""
        from runtime.model_adapters.ollama import OllamaAdapter

        mock_chat = _mock_model_with_tool_call(str(health_db))

        with patch.object(OllamaAdapter, "chat", mock_chat):
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "query"}],
                },
            )

        request_id = resp.json()["trace"]["request_id"]
        audit_resp = client.get(f"/v1/domekit/audit/{request_id}")
        events = [e["event"] for e in audit_resp.json()]

        assert "policy.block" not in events

    def test_health_endpoint(self, client: TestClient) -> None:
        """Health endpoint works with the health-poc manifest loaded."""
        resp = client.get("/v1/domekit/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

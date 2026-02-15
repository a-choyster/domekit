"""Unit tests for runtime/security.py heuristic detectors."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from contracts.audit import AuditEntry, AuditEvent
from runtime.security import detect_alerts


def _write_entries(entries: list[AuditEntry]) -> Path:
    """Write audit entries to a temp JSONL file and return the path."""
    p = Path(tempfile.mktemp(suffix=".jsonl"))
    with p.open("w") as f:
        for e in entries:
            f.write(e.model_dump_json() + "\n")
    return p


def _ts(minutes_ago: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)


class TestPathTraversal:
    def test_detects_path_traversal_in_tool_call(self):
        entries = [
            AuditEntry(
                request_id="r1", event=AuditEvent.TOOL_CALL,
                detail={"tool": "read_file", "arguments": {"path": "../../etc/passwd"}},
            ),
        ]
        path = _write_entries(entries)
        alerts = detect_alerts(path)
        assert len(alerts) == 1
        assert alerts[0]["type"] == "path_traversal"
        assert alerts[0]["severity"] == "high"
        path.unlink()

    def test_no_false_positive_on_normal_paths(self):
        entries = [
            AuditEntry(
                request_id="r1", event=AuditEvent.TOOL_CALL,
                detail={"tool": "read_file", "arguments": {"path": "apps/data/file.csv"}},
            ),
        ]
        path = _write_entries(entries)
        alerts = detect_alerts(path)
        assert len(alerts) == 0
        path.unlink()

    def test_detects_in_policy_block(self):
        entries = [
            AuditEntry(
                request_id="r1", event=AuditEvent.POLICY_BLOCK,
                detail={"tool": "read_file", "path": "../../../secret"},
            ),
        ]
        path = _write_entries(entries)
        alerts = [a for a in detect_alerts(path) if a["type"] == "path_traversal"]
        assert len(alerts) == 1
        path.unlink()


class TestSqlInjection:
    def test_detects_drop_table(self):
        entries = [
            AuditEntry(
                request_id="r1", event=AuditEvent.TOOL_CALL,
                detail={"tool": "sql_query", "arguments": {"query": "DROP TABLE users"}},
            ),
        ]
        path = _write_entries(entries)
        alerts = detect_alerts(path)
        assert any(a["type"] == "sql_injection" for a in alerts)
        assert any(a["severity"] == "critical" for a in alerts)
        path.unlink()

    def test_detects_union_select(self):
        entries = [
            AuditEntry(
                request_id="r1", event=AuditEvent.TOOL_CALL,
                detail={"tool": "sql_query", "arguments": {"query": "SELECT * FROM x UNION SELECT * FROM passwords"}},
            ),
        ]
        path = _write_entries(entries)
        alerts = [a for a in detect_alerts(path) if a["type"] == "sql_injection"]
        assert len(alerts) == 1
        path.unlink()

    def test_detects_comment_injection(self):
        entries = [
            AuditEntry(
                request_id="r1", event=AuditEvent.TOOL_CALL,
                detail={"tool": "sql_query", "arguments": {"query": "SELECT * FROM users; -- drop"}},
            ),
        ]
        path = _write_entries(entries)
        alerts = [a for a in detect_alerts(path) if a["type"] == "sql_injection"]
        assert len(alerts) == 1
        path.unlink()

    def test_no_false_positive_on_normal_query(self):
        entries = [
            AuditEntry(
                request_id="r1", event=AuditEvent.TOOL_CALL,
                detail={"tool": "sql_query", "arguments": {"query": "SELECT COUNT(*) FROM activities WHERE date LIKE '%2024%'"}},
            ),
        ]
        path = _write_entries(entries)
        alerts = [a for a in detect_alerts(path) if a["type"] == "sql_injection"]
        assert len(alerts) == 0
        path.unlink()


class TestBurstDenial:
    def test_detects_burst(self):
        now = datetime.now(timezone.utc)
        entries = [
            AuditEntry(
                ts=now + timedelta(seconds=i),
                request_id=f"r{i}", event=AuditEvent.POLICY_BLOCK,
                detail={"tool": "write_file"},
            )
            for i in range(6)
        ]
        path = _write_entries(entries)
        alerts = [a for a in detect_alerts(path) if a["type"] == "burst_denial"]
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "medium"
        path.unlink()

    def test_no_burst_with_few_blocks(self):
        now = datetime.now(timezone.utc)
        entries = [
            AuditEntry(
                ts=now + timedelta(seconds=i),
                request_id=f"r{i}", event=AuditEvent.POLICY_BLOCK,
                detail={"tool": "write_file"},
            )
            for i in range(3)
        ]
        path = _write_entries(entries)
        alerts = [a for a in detect_alerts(path) if a["type"] == "burst_denial"]
        assert len(alerts) == 0
        path.unlink()


class TestRepeatedDenial:
    def test_detects_repeated_denial(self):
        entries = [
            AuditEntry(
                request_id=f"r{i}", event=AuditEvent.POLICY_BLOCK,
                detail={"tool": "write_file"},
            )
            for i in range(4)
        ]
        path = _write_entries(entries)
        alerts = [a for a in detect_alerts(path) if a["type"] == "repeated_denial"]
        assert len(alerts) == 1
        assert "write_file" in alerts[0]["message"]
        path.unlink()

    def test_no_alert_for_single_block(self):
        entries = [
            AuditEntry(
                request_id="r1", event=AuditEvent.POLICY_BLOCK,
                detail={"tool": "write_file"},
            ),
        ]
        path = _write_entries(entries)
        alerts = [a for a in detect_alerts(path) if a["type"] == "repeated_denial"]
        assert len(alerts) == 0
        path.unlink()


class TestSinceFilter:
    def test_since_filters_old_entries(self):
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        recent = datetime.now(timezone.utc)
        entries = [
            AuditEntry(
                ts=old, request_id="r1", event=AuditEvent.TOOL_CALL,
                detail={"tool": "read_file", "arguments": {"path": "../../etc/passwd"}},
            ),
            AuditEntry(
                ts=recent, request_id="r2", event=AuditEvent.TOOL_CALL,
                detail={"tool": "read_file", "arguments": {"path": "safe/file.txt"}},
            ),
        ]
        path = _write_entries(entries)
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        alerts = detect_alerts(path, since=since)
        assert len(alerts) == 0  # old path traversal is filtered out
        path.unlink()


class TestEmptyLog:
    def test_empty_file(self):
        p = Path(tempfile.mktemp(suffix=".jsonl"))
        p.touch()
        alerts = detect_alerts(p)
        assert alerts == []
        p.unlink()

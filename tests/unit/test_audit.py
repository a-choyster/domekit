"""Unit tests for the audit logger and query helpers."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from contracts.audit import AuditEntry, AuditEvent
from runtime.audit.logger import JsonlAuditLogger
from runtime.audit import query as audit_query


# ── helpers ─────────────────────────────────────────────────────────


def _entry(
    request_id: str = "req-1",
    event: AuditEvent = AuditEvent.REQUEST_START,
    app: str = "test",
) -> AuditEntry:
    return AuditEntry(request_id=request_id, event=event, app=app)


# ── logger tests ────────────────────────────────────────────────────


class TestJsonlAuditLogger:
    def test_log_creates_file(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.jsonl"
        logger = JsonlAuditLogger(log_file)
        logger.log(_entry())
        assert log_file.exists()

    def test_log_appends_lines(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.jsonl"
        logger = JsonlAuditLogger(log_file)
        logger.log(_entry(request_id="r1"))
        logger.log(_entry(request_id="r2"))
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_query_by_request(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.jsonl"
        logger = JsonlAuditLogger(log_file)
        logger.log(_entry(request_id="r1", event=AuditEvent.REQUEST_START))
        logger.log(_entry(request_id="r2", event=AuditEvent.TOOL_CALL))
        logger.log(_entry(request_id="r1", event=AuditEvent.REQUEST_END))

        results = logger.query_by_request("r1")
        assert len(results) == 2
        assert all(e.request_id == "r1" for e in results)

    def test_query_by_event(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.jsonl"
        logger = JsonlAuditLogger(log_file)
        logger.log(_entry(event=AuditEvent.TOOL_CALL))
        logger.log(_entry(event=AuditEvent.REQUEST_START))
        logger.log(_entry(event=AuditEvent.TOOL_CALL))

        results = logger.query_by_event(AuditEvent.TOOL_CALL)
        assert len(results) == 2

    def test_query_by_event_limit(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.jsonl"
        logger = JsonlAuditLogger(log_file)
        for i in range(10):
            logger.log(_entry(request_id=f"r{i}", event=AuditEvent.TOOL_CALL))

        results = logger.query_by_event(AuditEvent.TOOL_CALL, limit=3)
        assert len(results) == 3
        assert results[0].request_id == "r7"

    def test_tail(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.jsonl"
        logger = JsonlAuditLogger(log_file)
        for i in range(10):
            logger.log(_entry(request_id=f"r{i}"))

        results = logger.tail(3)
        assert len(results) == 3
        assert results[0].request_id == "r7"

    def test_tail_empty_log(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.jsonl"
        logger = JsonlAuditLogger(log_file)
        results = logger.tail(5)
        assert results == []


# ── standalone query function tests ─────────────────────────────────


class TestAuditQueryFunctions:
    def test_query_by_request(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.jsonl"
        logger = JsonlAuditLogger(log_file)
        logger.log(_entry(request_id="r1", event=AuditEvent.REQUEST_START))
        logger.log(_entry(request_id="r2", event=AuditEvent.TOOL_CALL))

        results = audit_query.query_by_request(log_file, "r1")
        assert len(results) == 1

    def test_query_by_event(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.jsonl"
        logger = JsonlAuditLogger(log_file)
        logger.log(_entry(event=AuditEvent.POLICY_BLOCK))
        logger.log(_entry(event=AuditEvent.TOOL_CALL))

        results = audit_query.query_by_event(log_file, AuditEvent.POLICY_BLOCK)
        assert len(results) == 1

    def test_tail(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.jsonl"
        logger = JsonlAuditLogger(log_file)
        for i in range(5):
            logger.log(_entry(request_id=f"r{i}"))

        results = audit_query.tail(log_file, 2)
        assert len(results) == 2
        assert results[0].request_id == "r3"

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        log_file = tmp_path / "nonexistent.jsonl"
        assert audit_query.tail(log_file, 5) == []
        assert audit_query.query_by_request(log_file, "x") == []
        assert audit_query.query_by_event(log_file, AuditEvent.TOOL_CALL) == []

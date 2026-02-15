"""Unit tests for runtime/metrics.py aggregation functions."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from contracts.audit import AuditEntry, AuditEvent
from runtime.metrics import compute_metrics


def _write_entries(entries: list[AuditEntry]) -> Path:
    p = Path(tempfile.mktemp(suffix=".jsonl"))
    with p.open("w") as f:
        for e in entries:
            f.write(e.model_dump_json() + "\n")
    return p


def _ts(minutes_ago: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)


class TestThroughput:
    def test_buckets_requests(self):
        now = datetime.now(timezone.utc)
        entries = [
            AuditEntry(ts=now + timedelta(seconds=i * 10), request_id=f"r{i}", event=AuditEvent.REQUEST_START)
            for i in range(6)
        ]
        path = _write_entries(entries)
        m = compute_metrics(path, window_seconds=60)
        tp = m["throughput"]
        assert len(tp) >= 1
        assert sum(b["count"] for b in tp) == 6
        path.unlink()

    def test_empty_log(self):
        p = Path(tempfile.mktemp(suffix=".jsonl"))
        p.touch()
        m = compute_metrics(p)
        assert m["throughput"] == []
        p.unlink()


class TestLatency:
    def test_computes_percentiles(self):
        now = datetime.now(timezone.utc)
        entries = []
        for i in range(10):
            start = now + timedelta(minutes=i)
            end = start + timedelta(seconds=i + 1)  # latencies: 1s, 2s, ... 10s
            entries.append(AuditEntry(ts=start, request_id=f"r{i}", event=AuditEvent.REQUEST_START))
            entries.append(AuditEntry(ts=end, request_id=f"r{i}", event=AuditEvent.REQUEST_END))

        path = _write_entries(entries)
        m = compute_metrics(path)
        lat = m["latency"]
        assert lat["count"] == 10
        assert lat["p50"] > 0
        assert lat["p95"] >= lat["p50"]
        assert lat["p99"] >= lat["p95"]
        path.unlink()

    def test_no_latency_without_pairs(self):
        entries = [
            AuditEntry(request_id="r1", event=AuditEvent.REQUEST_START),
        ]
        path = _write_entries(entries)
        m = compute_metrics(path)
        assert m["latency"]["count"] == 0
        assert m["latency"]["p50"] == 0
        path.unlink()


class TestToolUsage:
    def test_counts_tools(self):
        entries = [
            AuditEntry(request_id="r1", event=AuditEvent.TOOL_CALL, detail={"tool": "sql_query"}),
            AuditEntry(request_id="r2", event=AuditEvent.TOOL_CALL, detail={"tool": "sql_query"}),
            AuditEntry(request_id="r3", event=AuditEvent.TOOL_CALL, detail={"tool": "read_file"}),
        ]
        path = _write_entries(entries)
        m = compute_metrics(path)
        usage = {t["tool"]: t["count"] for t in m["tool_usage"]}
        assert usage["sql_query"] == 2
        assert usage["read_file"] == 1
        path.unlink()

    def test_empty_when_no_tool_calls(self):
        entries = [
            AuditEntry(request_id="r1", event=AuditEvent.REQUEST_START),
        ]
        path = _write_entries(entries)
        m = compute_metrics(path)
        assert m["tool_usage"] == []
        path.unlink()


class TestErrorRates:
    def test_computes_block_rate(self):
        entries = [
            AuditEntry(request_id="r1", event=AuditEvent.REQUEST_START),
            AuditEntry(request_id="r2", event=AuditEvent.REQUEST_START),
            AuditEntry(request_id="r1", event=AuditEvent.POLICY_BLOCK, detail={"tool": "write_file"}),
        ]
        path = _write_entries(entries)
        m = compute_metrics(path)
        err = m["error_rates"]
        assert err["total_requests"] == 2
        assert err["policy_blocks"] == 1
        assert err["block_rate"] == 0.5
        path.unlink()


class TestSummary:
    def test_summary_counts(self):
        entries = [
            AuditEntry(request_id="r1", event=AuditEvent.REQUEST_START),
            AuditEntry(request_id="r1", event=AuditEvent.TOOL_CALL, detail={"tool": "sql_query"}),
            AuditEntry(request_id="r1", event=AuditEvent.TOOL_RESULT, detail={"tool": "sql_query"}),
            AuditEntry(request_id="r1", event=AuditEvent.REQUEST_END),
        ]
        path = _write_entries(entries)
        m = compute_metrics(path)
        s = m["summary"]
        assert s["total_entries"] == 4
        assert s["event_counts"]["request.start"] == 1
        assert s["event_counts"]["tool.call"] == 1
        path.unlink()


class TestSinceFilter:
    def test_filters_by_since(self):
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        recent = datetime.now(timezone.utc)
        entries = [
            AuditEntry(ts=old, request_id="r1", event=AuditEvent.REQUEST_START),
            AuditEntry(ts=recent, request_id="r2", event=AuditEvent.REQUEST_START),
        ]
        path = _write_entries(entries)
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        m = compute_metrics(path, since=since)
        assert m["summary"]["total_entries"] == 1
        path.unlink()

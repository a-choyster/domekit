"""Metrics aggregation for DomeKit observability.

Computes throughput, latency percentiles, tool usage, and error rates
from the audit log.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from contracts.audit import AuditEntry, AuditEvent
from runtime.audit.query import _read_all


def compute_metrics(
    log_path: str | Path,
    *,
    since: datetime | None = None,
    window_seconds: int = 60,
) -> dict[str, Any]:
    """Compute aggregated metrics from the audit log."""
    entries = _read_all(log_path)
    if since:
        entries = [e for e in entries if e.ts >= since]

    return {
        "throughput": _throughput_buckets(entries, window_seconds),
        "latency": _latency_percentiles(entries),
        "tool_usage": _tool_usage(entries),
        "error_rates": _error_rates(entries),
        "summary": _summary(entries),
    }


def _throughput_buckets(
    entries: list[AuditEntry], window_seconds: int
) -> list[dict[str, Any]]:
    """Bucket request.start events into time windows."""
    starts = [e for e in entries if e.event == AuditEvent.REQUEST_START]
    if not starts:
        return []

    starts.sort(key=lambda e: e.ts)
    bucket_start = starts[0].ts
    last_ts = starts[-1].ts
    buckets: list[dict[str, Any]] = []

    while bucket_start <= last_ts:
        bucket_end = bucket_start + timedelta(seconds=window_seconds)
        count = sum(1 for e in starts if bucket_start <= e.ts < bucket_end)
        buckets.append({
            "time": bucket_start.isoformat(),
            "count": count,
        })
        bucket_start = bucket_end

    return buckets


def _latency_percentiles(entries: list[AuditEntry]) -> dict[str, Any]:
    """Compute p50/p95/p99 latency by pairing request.start and request.end."""
    starts: dict[str, datetime] = {}
    durations: list[float] = []

    for e in entries:
        if e.event == AuditEvent.REQUEST_START:
            starts[e.request_id] = e.ts
        elif e.event == AuditEvent.REQUEST_END and e.request_id in starts:
            dt = (e.ts - starts[e.request_id]).total_seconds()
            durations.append(dt)

    if not durations:
        return {"p50": 0, "p95": 0, "p99": 0, "count": 0}

    durations.sort()
    n = len(durations)
    return {
        "p50": round(durations[int(n * 0.50)], 3),
        "p95": round(durations[int(min(n * 0.95, n - 1))], 3),
        "p99": round(durations[int(min(n * 0.99, n - 1))], 3),
        "count": n,
    }


def _tool_usage(entries: list[AuditEntry]) -> list[dict[str, Any]]:
    """Count tool calls by tool name."""
    counts: dict[str, int] = {}
    for e in entries:
        if e.event == AuditEvent.TOOL_CALL:
            tool = e.detail.get("tool", "unknown")
            counts[tool] = counts.get(tool, 0) + 1

    return [{"tool": t, "count": c} for t, c in sorted(counts.items(), key=lambda x: -x[1])]


def _error_rates(entries: list[AuditEntry]) -> dict[str, Any]:
    """Compute error and policy block rates."""
    total_requests = sum(1 for e in entries if e.event == AuditEvent.REQUEST_START)
    policy_blocks = sum(1 for e in entries if e.event == AuditEvent.POLICY_BLOCK)
    tool_calls = sum(1 for e in entries if e.event == AuditEvent.TOOL_CALL)

    return {
        "total_requests": total_requests,
        "policy_blocks": policy_blocks,
        "tool_calls": tool_calls,
        "block_rate": round(policy_blocks / max(total_requests, 1), 4),
    }


def _summary(entries: list[AuditEntry]) -> dict[str, Any]:
    """High-level summary stats."""
    if not entries:
        return {"total_entries": 0, "first_entry": None, "last_entry": None}

    sorted_entries = sorted(entries, key=lambda e: e.ts)
    event_counts: dict[str, int] = {}
    for e in entries:
        event_counts[e.event.value] = event_counts.get(e.event.value, 0) + 1

    return {
        "total_entries": len(entries),
        "first_entry": sorted_entries[0].ts.isoformat(),
        "last_entry": sorted_entries[-1].ts.isoformat(),
        "event_counts": event_counts,
    }

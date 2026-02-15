"""Security alert heuristics for DomeKit observability.

Scans audit log entries for suspicious patterns:
- Path traversal attempts (../ in file paths)
- SQL injection patterns in tool arguments
- Burst denial (many policy.block events in short window)
- Repeated denial clustering by tool name
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from contracts.audit import AuditEntry, AuditEvent
from runtime.audit.query import _read_all

# ── Pattern constants ────────────────────────────────────────────────

_PATH_TRAVERSAL_RE = re.compile(r"\.\./|\.\.\\")
_SQL_INJECTION_RE = re.compile(
    r"\b(DROP\s+TABLE|DELETE\s+FROM|UNION\s+SELECT|INSERT\s+INTO\s.*SELECT"
    r"|;\s*--|OR\s+1\s*=\s*1|'\s*OR\s+')",
    re.IGNORECASE,
)
_BURST_WINDOW_SECONDS = 60
_BURST_THRESHOLD = 5


def detect_alerts(
    log_path: str | Path,
    *,
    since: datetime | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Run all heuristic detectors and return alerts sorted by time (newest first)."""
    entries = _read_all(log_path)
    if since:
        entries = [e for e in entries if e.ts >= since]

    alerts: list[dict[str, Any]] = []
    alerts.extend(_detect_path_traversal(entries))
    alerts.extend(_detect_sql_injection(entries))
    alerts.extend(_detect_burst_denial(entries))
    alerts.extend(_detect_repeated_denial(entries))

    alerts.sort(key=lambda a: a["ts"], reverse=True)
    return alerts[:limit]


def _detect_path_traversal(entries: list[AuditEntry]) -> list[dict[str, Any]]:
    alerts = []
    for e in entries:
        if e.event not in (AuditEvent.TOOL_CALL, AuditEvent.POLICY_BLOCK):
            continue
        detail_str = str(e.detail)
        if _PATH_TRAVERSAL_RE.search(detail_str):
            alerts.append({
                "type": "path_traversal",
                "severity": "high",
                "ts": e.ts.isoformat(),
                "request_id": e.request_id,
                "event": e.event.value,
                "detail": e.detail,
                "message": "Path traversal pattern detected in tool arguments",
            })
    return alerts


def _detect_sql_injection(entries: list[AuditEntry]) -> list[dict[str, Any]]:
    alerts = []
    for e in entries:
        if e.event not in (AuditEvent.TOOL_CALL, AuditEvent.POLICY_BLOCK):
            continue
        args = e.detail.get("arguments", {})
        query = args.get("query", "")
        if _SQL_INJECTION_RE.search(query):
            alerts.append({
                "type": "sql_injection",
                "severity": "critical",
                "ts": e.ts.isoformat(),
                "request_id": e.request_id,
                "event": e.event.value,
                "detail": e.detail,
                "message": f"SQL injection pattern detected: {query[:120]}",
            })
    return alerts


def _detect_burst_denial(entries: list[AuditEntry]) -> list[dict[str, Any]]:
    blocks = [e for e in entries if e.event == AuditEvent.POLICY_BLOCK]
    if len(blocks) < _BURST_THRESHOLD:
        return []

    alerts = []
    for i in range(len(blocks)):
        window_start = blocks[i].ts
        window_end = window_start + timedelta(seconds=_BURST_WINDOW_SECONDS)
        window_blocks = [b for b in blocks[i:] if b.ts <= window_end]
        if len(window_blocks) >= _BURST_THRESHOLD:
            alerts.append({
                "type": "burst_denial",
                "severity": "medium",
                "ts": blocks[i].ts.isoformat(),
                "request_id": blocks[i].request_id,
                "event": "policy.block",
                "detail": {"count": len(window_blocks), "window_seconds": _BURST_WINDOW_SECONDS},
                "message": f"{len(window_blocks)} policy blocks within {_BURST_WINDOW_SECONDS}s window",
            })
            break  # Report only the first burst
    return alerts


def _detect_repeated_denial(entries: list[AuditEntry]) -> list[dict[str, Any]]:
    blocks = [e for e in entries if e.event == AuditEvent.POLICY_BLOCK]
    tool_counts: dict[str, int] = {}
    for b in blocks:
        tool = b.detail.get("tool", "unknown")
        tool_counts[tool] = tool_counts.get(tool, 0) + 1

    alerts = []
    for tool, count in tool_counts.items():
        if count >= 3:
            alerts.append({
                "type": "repeated_denial",
                "severity": "medium",
                "ts": blocks[-1].ts.isoformat() if blocks else datetime.now(timezone.utc).isoformat(),
                "request_id": "",
                "event": "policy.block",
                "detail": {"tool": tool, "count": count},
                "message": f"Tool '{tool}' blocked {count} times — possible probing",
            })
    return alerts

"""Audit query helpers (Phase 0).

Convenience functions that wrap the AuditLogger query methods.
These exist so other modules can call standalone functions instead
of needing a logger instance for read-only queries.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from contracts.audit import AuditEntry, AuditEvent


def query_by_request(log_path: str | Path, request_id: str) -> list[AuditEntry]:
    """Return all audit entries for a given request_id."""
    return [e for e in _read_all(log_path) if e.request_id == request_id]


def query_by_event(
    log_path: str | Path, event: AuditEvent, limit: int = 100
) -> list[AuditEntry]:
    """Return recent entries of a given event type."""
    matches = [e for e in _read_all(log_path) if e.event == event]
    return matches[-limit:]


def tail(log_path: str | Path, n: int = 20) -> list[AuditEntry]:
    """Return the last N entries from the audit log."""
    entries = _read_all(log_path)
    return entries[-n:]


def query_filtered(
    log_path: str | Path,
    *,
    event: AuditEvent | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    request_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditEntry], int]:
    """Return paginated, filtered audit entries.

    Returns (entries, total_matching_count).
    """
    all_entries = _read_all(log_path)
    filtered = all_entries

    if event is not None:
        filtered = [e for e in filtered if e.event == event]
    if request_id is not None:
        filtered = [e for e in filtered if e.request_id == request_id]
    if since is not None:
        filtered = [e for e in filtered if e.ts >= since]
    if until is not None:
        filtered = [e for e in filtered if e.ts <= until]

    total = len(filtered)
    # Most recent first
    filtered.sort(key=lambda e: e.ts, reverse=True)
    page = filtered[offset : offset + limit]
    return page, total


async def stream_tail(
    log_path: str | Path, poll_interval: float = 0.5
) -> AsyncIterator[AuditEntry]:
    """Yield new audit entries as they are appended to the log file.

    Polls the JSONL file for new lines every *poll_interval* seconds.
    """
    p = Path(log_path)
    # Start at end of file
    pos = p.stat().st_size if p.exists() else 0

    while True:
        if p.exists() and p.stat().st_size > pos:
            with p.open("r", encoding="utf-8") as f:
                f.seek(pos)
                for line in f:
                    line = line.strip()
                    if line:
                        yield AuditEntry(**json.loads(line))
                pos = f.tell()
        await asyncio.sleep(poll_interval)


def _read_all(log_path: str | Path) -> list[AuditEntry]:
    p = Path(log_path)
    if not p.exists():
        return []
    entries: list[AuditEntry] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entries.append(AuditEntry(**json.loads(line)))
    return entries

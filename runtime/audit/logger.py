"""Append-only JSONL audit logger (Phase 0)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from contracts.audit import AuditEntry, AuditEvent, AuditLogger


class JsonlAuditLogger(AuditLogger):
    """Thread-safe, append-only JSONL audit logger."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        # Ensure parent directory exists
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, entry: AuditEntry) -> None:
        line = entry.model_dump_json() + "\n"
        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line)

    def query_by_request(self, request_id: str) -> list[AuditEntry]:
        return [e for e in self._read_all() if e.request_id == request_id]

    def query_by_event(self, event: AuditEvent, limit: int = 100) -> list[AuditEntry]:
        matches = [e for e in self._read_all() if e.event == event]
        return matches[-limit:]

    def tail(self, n: int = 20) -> list[AuditEntry]:
        entries = self._read_all()
        return entries[-n:]

    # ── internal ────────────────────────────────────────────────────

    def _read_all(self) -> list[AuditEntry]:
        if not self._path.exists():
            return []
        entries: list[AuditEntry] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entries.append(AuditEntry(**json.loads(line)))
        return entries

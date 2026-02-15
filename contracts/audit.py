"""Audit logging contracts (Phase 0).

Append-only JSONL — one record per event.
Event types and minimum fields per the Phase 0 spec §12.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AuditEvent(str, Enum):
    REQUEST_START = "request.start"
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"
    REQUEST_END = "request.end"
    POLICY_BLOCK = "policy.block"


class AuditEntry(BaseModel):
    """A single audit log record."""

    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str
    event: AuditEvent
    app: str = ""
    model: str = ""
    policy_mode: str = "local_only"
    detail: dict[str, Any] = {}  # tool name, table name, file path, etc.


class AuditLogger(ABC):
    """Interface for the append-only audit logger."""

    @abstractmethod
    def log(self, entry: AuditEntry) -> None:
        """Append an entry to the audit log."""
        ...

    @abstractmethod
    def query_by_request(self, request_id: str) -> list[AuditEntry]:
        """Return all entries for a given request_id."""
        ...

    @abstractmethod
    def query_by_event(self, event: AuditEvent, limit: int = 100) -> list[AuditEntry]:
        """Return recent entries of a given event type."""
        ...

    @abstractmethod
    def tail(self, n: int = 20) -> list[AuditEntry]:
        """Return the last N entries."""
        ...

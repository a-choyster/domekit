"""Tool SDK contracts (Phase 0).

Every DomeKit tool implements BaseTool.  The runtime validates inputs,
checks policy, executes the tool, and logs the result.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


# ── Data models ──────────────────────────────────────────────────────


class ToolDefinition(BaseModel):
    """OpenAI function-calling compatible schema for a tool."""

    name: str
    description: str
    input_schema: dict[str, Any]   # JSON Schema
    output_schema: dict[str, Any] = {}  # JSON Schema (optional Phase 0)
    permissions: list[str] = []    # e.g. ["data:sqlite", "fs:read"]


class ToolInput(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    call_id: str


class ToolOutput(BaseModel):
    call_id: str
    tool_name: str
    result: Any = None
    error: str | None = None
    success: bool = True


# ── Context passed to every tool invocation ──────────────────────────


@dataclass
class ToolContext:
    """Runtime context supplied to a tool's run() method."""

    request_id: str
    app_name: str = ""
    policy_mode: str = "local_only"
    manifest_data_paths: dict[str, Any] = field(default_factory=dict)


# ── Abstract base class ─────────────────────────────────────────────


class BaseTool(ABC):
    """Abstract base class that every DomeKit tool must implement."""

    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return the tool's function-calling schema."""
        ...

    @abstractmethod
    async def run(self, ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
        """Execute the tool. Called by the runtime after policy check."""
        ...

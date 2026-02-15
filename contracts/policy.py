"""Policy engine contracts (Phase 0).

The policy engine enforces manifest rules at runtime.
Three check methods per spec §4: tool, data access, network.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel

from contracts.manifest import Manifest
from contracts.tool_sdk import ToolInput


class PolicyVerdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class PolicyDecision(BaseModel):
    verdict: PolicyVerdict
    rule: str = ""      # which rule triggered the decision
    reason: str = ""    # human-readable explanation


class PolicyEngine(ABC):
    """Interface that the runtime policy engine must implement."""

    @abstractmethod
    def load_manifest(self, manifest: Manifest) -> None:
        """Load or reload policy rules from a parsed manifest."""
        ...

    @abstractmethod
    def check_tool(self, tool_input: ToolInput) -> PolicyDecision:
        """Is this tool call allowed?"""
        ...

    @abstractmethod
    def check_data_access(self, path: str, access: str = "read") -> PolicyDecision:
        """Is access to this data path (file or DB) allowed?"""
        ...

    @abstractmethod
    def check_network(self, host: str) -> PolicyDecision:
        """Is outbound network to this host allowed?"""
        ...

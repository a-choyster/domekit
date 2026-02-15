"""Policy engine implementation (Phase 0).

Enforces manifest rules for tool calls, data access, and network.
"""

from __future__ import annotations

import fnmatch

from contracts.manifest import Manifest, PolicyMode
from contracts.policy import PolicyDecision, PolicyEngine, PolicyVerdict
from contracts.tool_sdk import ToolInput


class DomeKitPolicyEngine(PolicyEngine):
    """Concrete policy engine driven by a parsed Manifest."""

    def __init__(self) -> None:
        self._manifest: Manifest | None = None

    def load_manifest(self, manifest: Manifest) -> None:
        self._manifest = manifest

    @property
    def _mode(self) -> PolicyMode:
        if self._manifest is None:
            return PolicyMode.LOCAL_ONLY
        return self._manifest.runtime.policy_mode

    # ── tool check ──────────────────────────────────────────────────

    def check_tool(self, tool_input: ToolInput) -> PolicyDecision:
        if self._manifest is None:
            return PolicyDecision(
                verdict=PolicyVerdict.DENY,
                rule="no_manifest",
                reason="No manifest loaded",
            )

        # Developer mode: allow all tools
        if self._mode == PolicyMode.DEVELOPER:
            return PolicyDecision(
                verdict=PolicyVerdict.ALLOW,
                rule="developer_mode",
                reason="Developer mode allows all tools",
            )

        allowed = self._manifest.policy.tools.allow
        if tool_input.tool_name in allowed:
            return PolicyDecision(
                verdict=PolicyVerdict.ALLOW,
                rule="tools.allow",
                reason=f"Tool '{tool_input.tool_name}' is in the allow list",
            )

        return PolicyDecision(
            verdict=PolicyVerdict.DENY,
            rule="tools.allow",
            reason=f"Tool '{tool_input.tool_name}' is not in the allow list",
        )

    # ── data access check ───────────────────────────────────────────

    def check_data_access(self, path: str, access: str = "read") -> PolicyDecision:
        if self._manifest is None:
            return PolicyDecision(
                verdict=PolicyVerdict.DENY,
                rule="no_manifest",
                reason="No manifest loaded",
            )

        # Developer mode: allow all data access
        if self._mode == PolicyMode.DEVELOPER:
            return PolicyDecision(
                verdict=PolicyVerdict.ALLOW,
                rule="developer_mode",
                reason="Developer mode allows all data access",
            )

        policy = self._manifest.policy

        if access == "read":
            # Check sqlite allow list
            if path in policy.data.sqlite.allow:
                return PolicyDecision(
                    verdict=PolicyVerdict.ALLOW,
                    rule="data.sqlite.allow",
                    reason=f"SQLite path '{path}' is allowed",
                )
            # Check filesystem allow_read (glob patterns)
            for pattern in policy.data.filesystem.allow_read:
                if fnmatch.fnmatch(path, pattern):
                    return PolicyDecision(
                        verdict=PolicyVerdict.ALLOW,
                        rule="data.filesystem.allow_read",
                        reason=f"Path '{path}' matches read pattern '{pattern}'",
                    )
            return PolicyDecision(
                verdict=PolicyVerdict.DENY,
                rule="data.read",
                reason=f"Path '{path}' is not in any read allow list",
            )

        if access == "write":
            for pattern in policy.data.filesystem.allow_write:
                if fnmatch.fnmatch(path, pattern):
                    return PolicyDecision(
                        verdict=PolicyVerdict.ALLOW,
                        rule="data.filesystem.allow_write",
                        reason=f"Path '{path}' matches write pattern '{pattern}'",
                    )
            return PolicyDecision(
                verdict=PolicyVerdict.DENY,
                rule="data.write",
                reason=f"Path '{path}' is not in the write allow list",
            )

        if access == "vector_read":
            for pattern in policy.data.vector.allow:
                if fnmatch.fnmatch(path, pattern):
                    return PolicyDecision(
                        verdict=PolicyVerdict.ALLOW,
                        rule="data.vector.allow",
                        reason=f"Collection '{path}' matches vector read pattern '{pattern}'",
                    )
            return PolicyDecision(
                verdict=PolicyVerdict.DENY,
                rule="data.vector_read",
                reason=f"Collection '{path}' is not in the vector allow list",
            )

        if access == "vector_write":
            for pattern in policy.data.vector.allow_write:
                if fnmatch.fnmatch(path, pattern):
                    return PolicyDecision(
                        verdict=PolicyVerdict.ALLOW,
                        rule="data.vector.allow_write",
                        reason=f"Collection '{path}' matches vector write pattern '{pattern}'",
                    )
            return PolicyDecision(
                verdict=PolicyVerdict.DENY,
                rule="data.vector_write",
                reason=f"Collection '{path}' is not in the vector write allow list",
            )

        return PolicyDecision(
            verdict=PolicyVerdict.DENY,
            rule="data.unknown_access",
            reason=f"Unknown access type '{access}'",
        )

    # ── network check ───────────────────────────────────────────────

    def check_network(self, host: str) -> PolicyDecision:
        if self._manifest is None:
            return PolicyDecision(
                verdict=PolicyVerdict.DENY,
                rule="no_manifest",
                reason="No manifest loaded",
            )

        # Developer mode: allow all network
        if self._mode == PolicyMode.DEVELOPER:
            return PolicyDecision(
                verdict=PolicyVerdict.ALLOW,
                rule="developer_mode",
                reason="Developer mode allows all network access",
            )

        network = self._manifest.policy.network

        if network.outbound == "allow":
            return PolicyDecision(
                verdict=PolicyVerdict.ALLOW,
                rule="network.outbound",
                reason="Outbound network is globally allowed",
            )

        # outbound == "deny" (default): only allow listed domains
        if host in network.allow_domains:
            return PolicyDecision(
                verdict=PolicyVerdict.ALLOW,
                rule="network.allow_domains",
                reason=f"Host '{host}' is in allow_domains",
            )

        return PolicyDecision(
            verdict=PolicyVerdict.DENY,
            rule="network.outbound",
            reason=f"Outbound denied; host '{host}' is not in allow_domains",
        )

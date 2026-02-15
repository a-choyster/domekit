"""Unit tests for the policy engine."""

from __future__ import annotations

import pytest

from contracts.manifest import (
    AppInfo,
    DataFilesystemPolicy,
    DataPolicy,
    DataSqlitePolicy,
    Manifest,
    NetworkPolicy,
    Policy,
    PolicyMode,
    RuntimeConfig,
    ToolsPolicy,
)
from contracts.policy import PolicyVerdict
from contracts.tool_sdk import ToolInput
from runtime.policy import DomeKitPolicyEngine


# ── helpers ─────────────────────────────────────────────────────────


def _make_manifest(
    *,
    mode: PolicyMode = PolicyMode.LOCAL_ONLY,
    tools_allow: list[str] | None = None,
    fs_read: list[str] | None = None,
    fs_write: list[str] | None = None,
    sqlite_allow: list[str] | None = None,
    outbound: str = "deny",
    allow_domains: list[str] | None = None,
) -> Manifest:
    return Manifest(
        app=AppInfo(name="test-app"),
        runtime=RuntimeConfig(policy_mode=mode),
        policy=Policy(
            tools=ToolsPolicy(allow=tools_allow or []),
            data=DataPolicy(
                filesystem=DataFilesystemPolicy(
                    allow_read=fs_read or [],
                    allow_write=fs_write or [],
                ),
                sqlite=DataSqlitePolicy(allow=sqlite_allow or []),
            ),
            network=NetworkPolicy(
                outbound=outbound,
                allow_domains=allow_domains or [],
            ),
        ),
    )


def _tool(name: str) -> ToolInput:
    return ToolInput(tool_name=name, arguments={}, call_id="test-1")


# ── tool checks ─────────────────────────────────────────────────────


class TestToolPolicy:
    def test_allow_listed_tool(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(tools_allow=["sql_query"]))
        decision = engine.check_tool(_tool("sql_query"))
        assert decision.verdict == PolicyVerdict.ALLOW

    def test_deny_unlisted_tool(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(tools_allow=["sql_query"]))
        decision = engine.check_tool(_tool("dangerous_tool"))
        assert decision.verdict == PolicyVerdict.DENY

    def test_deny_when_no_manifest(self) -> None:
        engine = DomeKitPolicyEngine()
        decision = engine.check_tool(_tool("sql_query"))
        assert decision.verdict == PolicyVerdict.DENY

    def test_developer_mode_allows_all_tools(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(mode=PolicyMode.DEVELOPER))
        decision = engine.check_tool(_tool("any_tool"))
        assert decision.verdict == PolicyVerdict.ALLOW


# ── data access checks ──────────────────────────────────────────────


class TestDataAccessPolicy:
    def test_allow_sqlite_read(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(sqlite_allow=["health.db"]))
        decision = engine.check_data_access("health.db", "read")
        assert decision.verdict == PolicyVerdict.ALLOW

    def test_allow_fs_read_glob(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(fs_read=["data/*.csv"]))
        decision = engine.check_data_access("data/report.csv", "read")
        assert decision.verdict == PolicyVerdict.ALLOW

    def test_deny_fs_read_no_match(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(fs_read=["data/*.csv"]))
        decision = engine.check_data_access("/etc/passwd", "read")
        assert decision.verdict == PolicyVerdict.DENY

    def test_allow_fs_write(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(fs_write=["output/*"]))
        decision = engine.check_data_access("output/result.json", "write")
        assert decision.verdict == PolicyVerdict.ALLOW

    def test_deny_fs_write_no_match(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(fs_write=["output/*"]))
        decision = engine.check_data_access("secrets/key.pem", "write")
        assert decision.verdict == PolicyVerdict.DENY

    def test_developer_mode_allows_all_data(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(mode=PolicyMode.DEVELOPER))
        decision = engine.check_data_access("/any/path", "write")
        assert decision.verdict == PolicyVerdict.ALLOW

    def test_unknown_access_type_denied(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest())
        decision = engine.check_data_access("file.txt", "execute")
        assert decision.verdict == PolicyVerdict.DENY


# ── network checks ──────────────────────────────────────────────────


class TestNetworkPolicy:
    def test_deny_outbound_by_default(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest())
        decision = engine.check_network("example.com")
        assert decision.verdict == PolicyVerdict.DENY

    def test_allow_listed_domain(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(allow_domains=["api.example.com"]))
        decision = engine.check_network("api.example.com")
        assert decision.verdict == PolicyVerdict.ALLOW

    def test_deny_unlisted_domain(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(allow_domains=["api.example.com"]))
        decision = engine.check_network("evil.com")
        assert decision.verdict == PolicyVerdict.DENY

    def test_allow_all_outbound(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(outbound="allow"))
        decision = engine.check_network("anywhere.com")
        assert decision.verdict == PolicyVerdict.ALLOW

    def test_developer_mode_allows_network(self) -> None:
        engine = DomeKitPolicyEngine()
        engine.load_manifest(_make_manifest(mode=PolicyMode.DEVELOPER))
        decision = engine.check_network("anywhere.com")
        assert decision.verdict == PolicyVerdict.ALLOW

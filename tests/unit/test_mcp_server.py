"""Unit tests for the DomeKit MCP server."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from contracts.audit import AuditEntry, AuditEvent
from contracts.manifest import (
    AppInfo,
    AuditConfig,
    DataFilesystemPolicy,
    DataPolicy,
    DataSqlitePolicy,
    DataVectorPolicy,
    Manifest,
    Policy,
    PolicyMode,
    RuntimeConfig,
    ToolsPolicy,
    VectorConfig,
)
from runtime.audit.logger import JsonlAuditLogger
from runtime.mcp_helpers import DomeKitComponents, init_domekit
from runtime.mcp_server import _build_tool_context, _run_tool, mcp
from runtime.policy import DomeKitPolicyEngine
from runtime.tools.registry import create_default_registry


# ── helpers ────────────────────────────────────────────────────────────


def _make_manifest(
    *,
    tmp_path: Path,
    mode: PolicyMode = PolicyMode.LOCAL_ONLY,
    tools_allow: list[str] | None = None,
    sqlite_allow: list[str] | None = None,
    fs_read: list[str] | None = None,
    fs_write: list[str] | None = None,
    vector_allow: list[str] | None = None,
    vector_allow_write: list[str] | None = None,
) -> Manifest:
    return Manifest(
        app=AppInfo(name="mcp-test-app"),
        runtime=RuntimeConfig(policy_mode=mode),
        policy=Policy(
            tools=ToolsPolicy(allow=tools_allow or []),
            data=DataPolicy(
                sqlite=DataSqlitePolicy(allow=sqlite_allow or []),
                filesystem=DataFilesystemPolicy(
                    allow_read=fs_read or [],
                    allow_write=fs_write or [],
                ),
                vector=DataVectorPolicy(
                    allow=vector_allow or [],
                    allow_write=vector_allow_write or [],
                ),
            ),
        ),
        audit=AuditConfig(path=str(tmp_path / "test_audit.jsonl")),
        vector_db=VectorConfig(backend="none"),
    )


def _make_components(manifest: Manifest, tmp_path: Path) -> DomeKitComponents:
    policy = DomeKitPolicyEngine()
    policy.load_manifest(manifest)
    registry = create_default_registry()
    logger = JsonlAuditLogger(manifest.audit.path)
    return DomeKitComponents(
        manifest=manifest,
        policy=policy,
        registry=registry,
        logger=logger,
    )


def _read_audit_log(path: str | Path) -> list[AuditEntry]:
    p = Path(path)
    if not p.exists():
        return []
    entries = []
    for line in p.read_text().strip().splitlines():
        if line:
            entries.append(AuditEntry(**json.loads(line)))
    return entries


# ── MCP tool registration ─────────────────────────────────────────────


class TestMcpToolRegistration:
    def test_all_five_tools_registered(self) -> None:
        """MCP server exposes all 5 DomeKit tools."""
        tool_names = set()
        for tool in mcp._tool_manager._tools.values():
            tool_names.add(tool.name)
        expected = {"sql_query", "read_file", "write_file", "vector_search", "vector_manage"}
        assert expected == tool_names

    def test_tools_have_descriptions(self) -> None:
        """Each MCP tool has a non-empty description."""
        for tool in mcp._tool_manager._tools.values():
            assert tool.description, f"Tool {tool.name} has no description"


# ── sql_query via MCP ──────────────────────────────────────────────────


class TestMcpSqlQuery:
    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> str:
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        conn.executemany("INSERT INTO t (val) VALUES (?)", [(f"row{i}",) for i in range(5)])
        conn.commit()
        conn.close()
        return str(db)

    @pytest.mark.asyncio
    async def test_allowed_query_returns_results(self, tmp_path: Path, db_path: str) -> None:
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=["sql_query"],
            sqlite_allow=[db_path],
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool("sql_query", {"db_path": db_path, "query": "SELECT * FROM t"})
            data = json.loads(result)
            assert data["success"] is True
            assert len(data["result"]["rows"]) == 5
        finally:
            mod._components = None

    @pytest.mark.asyncio
    async def test_disallowed_db_returns_error(self, tmp_path: Path, db_path: str) -> None:
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=["sql_query"],
            sqlite_allow=["/some/other/path.db"],
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool("sql_query", {"db_path": db_path, "query": "SELECT 1"})
            data = json.loads(result)
            assert data["success"] is False
            assert "not allowed" in data["error"]
        finally:
            mod._components = None

    @pytest.mark.asyncio
    async def test_tool_not_in_allow_list_returns_policy_denial(self, tmp_path: Path, db_path: str) -> None:
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=["read_file"],  # sql_query NOT allowed
            sqlite_allow=[db_path],
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool("sql_query", {"db_path": db_path, "query": "SELECT 1"})
            assert "Policy denied" in result
        finally:
            mod._components = None


# ── read_file via MCP ──────────────────────────────────────────────────


class TestMcpReadFile:
    @pytest.mark.asyncio
    async def test_allowed_read_returns_content(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_text("hello mcp")
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=["read_file"],
            fs_read=[str(tmp_path)],
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool("read_file", {"path": str(f)})
            data = json.loads(result)
            assert data["success"] is True
            assert data["result"] == "hello mcp"
        finally:
            mod._components = None

    @pytest.mark.asyncio
    async def test_disallowed_path_returns_error(self, tmp_path: Path) -> None:
        f = tmp_path / "secret.txt"
        f.write_text("secret")
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=["read_file"],
            fs_read=["/some/other/prefix"],
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool("read_file", {"path": str(f)})
            data = json.loads(result)
            assert data["success"] is False
            assert "not allowed" in data["error"]
        finally:
            mod._components = None

    @pytest.mark.asyncio
    async def test_tool_policy_denial(self, tmp_path: Path) -> None:
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=["sql_query"],  # read_file NOT allowed
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool("read_file", {"path": "/tmp/anything"})
            assert "Policy denied" in result
        finally:
            mod._components = None


# ── write_file via MCP ─────────────────────────────────────────────────


class TestMcpWriteFile:
    @pytest.mark.asyncio
    async def test_allowed_write(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=["write_file"],
            fs_write=[str(tmp_path)],
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool("write_file", {"path": str(target), "content": "written via mcp"})
            data = json.loads(result)
            assert data["success"] is True
            assert target.read_text() == "written via mcp"
        finally:
            mod._components = None

    @pytest.mark.asyncio
    async def test_write_policy_denial(self, tmp_path: Path) -> None:
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=[],  # write_file NOT allowed
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool("write_file", {"path": "/tmp/nope.txt", "content": "x"})
            assert "Policy denied" in result
        finally:
            mod._components = None


# ── vector_search via MCP ──────────────────────────────────────────────


class TestMcpVectorSearch:
    @pytest.mark.asyncio
    async def test_vector_search_policy_denial(self, tmp_path: Path) -> None:
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=[],  # vector_search NOT allowed
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool("vector_search", {"collection": "test", "query": "hello"})
            assert "Policy denied" in result
        finally:
            mod._components = None

    @pytest.mark.asyncio
    async def test_vector_search_collection_not_allowed(self, tmp_path: Path) -> None:
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=["vector_search"],
            vector_allow=["allowed-collection"],
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool("vector_search", {"collection": "secret-data", "query": "hello"})
            data = json.loads(result)
            assert data["success"] is False
            assert "not allowed" in data["error"]
        finally:
            mod._components = None


# ── vector_manage via MCP ──────────────────────────────────────────────


class TestMcpVectorManage:
    @pytest.mark.asyncio
    async def test_vector_manage_policy_denial(self, tmp_path: Path) -> None:
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=[],  # vector_manage NOT allowed
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool(
                "vector_manage",
                {"collection": "test", "operation": "insert", "documents": []},
            )
            assert "Policy denied" in result
        finally:
            mod._components = None

    @pytest.mark.asyncio
    async def test_vector_manage_collection_write_not_allowed(self, tmp_path: Path) -> None:
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=["vector_manage"],
            vector_allow_write=[],
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            result = await _run_tool(
                "vector_manage",
                {"collection": "test", "operation": "insert", "documents": [{"text": "hi"}]},
            )
            data = json.loads(result)
            assert data["success"] is False
            assert "not allowed" in data["error"].lower()
        finally:
            mod._components = None


# ── Audit logging ──────────────────────────────────────────────────────


class TestMcpAuditLogging:
    @pytest.mark.asyncio
    async def test_successful_call_writes_audit_entries(self, tmp_path: Path) -> None:
        db = tmp_path / "audit_test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=["sql_query"],
            sqlite_allow=[str(db)],
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            await _run_tool("sql_query", {"db_path": str(db), "query": "SELECT * FROM t"})
        finally:
            mod._components = None

        entries = _read_audit_log(manifest.audit.path)
        events = [e.event for e in entries]
        assert AuditEvent.TOOL_CALL in events
        assert AuditEvent.TOOL_RESULT in events
        # Verify transport field
        for e in entries:
            assert e.detail.get("transport") == "mcp"

    @pytest.mark.asyncio
    async def test_policy_block_writes_audit_entry(self, tmp_path: Path) -> None:
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=[],  # nothing allowed
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            await _run_tool("sql_query", {"db_path": "anything.db", "query": "SELECT 1"})
        finally:
            mod._components = None

        entries = _read_audit_log(manifest.audit.path)
        assert len(entries) == 1
        assert entries[0].event == AuditEvent.POLICY_BLOCK
        assert entries[0].detail["tool"] == "sql_query"
        assert entries[0].detail["transport"] == "mcp"


# ── mcp_helpers ────────────────────────────────────────────────────────


class TestMcpHelpers:
    def test_init_domekit_loads_manifest(self, tmp_path: Path) -> None:
        manifest_file = tmp_path / "domekit.yaml"
        manifest_file.write_text(
            "app:\n  name: helper-test\npolicy:\n  tools:\n    allow: [sql_query]\n"
        )

        components = init_domekit(str(manifest_file))
        assert components.manifest.app.name == "helper-test"
        assert "sql_query" in components.registry.list_tools()
        assert components.policy is not None
        assert components.logger is not None

    def test_build_tool_context(self, tmp_path: Path) -> None:
        manifest = _make_manifest(
            tmp_path=tmp_path,
            tools_allow=["sql_query"],
            sqlite_allow=["test.db"],
            fs_read=["/tmp"],
            fs_write=["/tmp/out"],
            vector_allow=["coll-a"],
            vector_allow_write=["coll-b"],
        )
        components = _make_components(manifest, tmp_path)

        import runtime.mcp_server as mod
        mod._components = components
        try:
            ctx = _build_tool_context(components, "req-123")
            assert ctx.request_id == "req-123"
            assert ctx.app_name == "mcp-test-app"
            assert ctx.manifest_data_paths["sqlite_allow"] == ["test.db"]
            assert ctx.manifest_data_paths["fs_allow_read"] == ["/tmp"]
            assert ctx.manifest_data_paths["fs_allow_write"] == ["/tmp/out"]
            assert ctx.manifest_data_paths["vector_allow"] == ["coll-a"]
            assert ctx.manifest_data_paths["vector_allow_write"] == ["coll-b"]
        finally:
            mod._components = None

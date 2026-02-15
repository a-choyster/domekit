"""Unit tests for the DomeKit tool SDK, registry, and built-in tools."""

from __future__ import annotations

import sqlite3
import textwrap
from pathlib import Path

import pytest

from contracts.tool_sdk import BaseTool, ToolContext, ToolDefinition, ToolOutput
from runtime.tools.base import validate_args
from runtime.tools.registry import ToolRegistry, create_default_registry
from runtime.tools.sql_query import SqlQueryTool
from runtime.tools.read_file import ReadFileTool
from runtime.tools.write_file import WriteFileTool


# ── Helpers ─────────────────────────────────────────────────────────


def _make_ctx(
    *,
    sqlite_allow: list[str] | None = None,
    fs_allow_read: list[str] | None = None,
    fs_allow_write: list[str] | None = None,
    max_rows: int | None = None,
    max_bytes: int | None = None,
) -> ToolContext:
    data: dict = {}
    if sqlite_allow is not None:
        data["sqlite_allow"] = sqlite_allow
    if fs_allow_read is not None:
        data["fs_allow_read"] = fs_allow_read
    if fs_allow_write is not None:
        data["fs_allow_write"] = fs_allow_write
    if max_rows is not None:
        data["max_rows"] = max_rows
    if max_bytes is not None:
        data["max_bytes"] = max_bytes
    return ToolContext(request_id="test-req-1", manifest_data_paths=data)


# ── Registry tests ──────────────────────────────────────────────────


class TestToolRegistry:
    def test_register_and_get(self) -> None:
        reg = ToolRegistry()
        tool = SqlQueryTool()
        reg.register(tool)
        assert reg.get("sql_query") is tool

    def test_get_missing_raises(self) -> None:
        reg = ToolRegistry()
        with pytest.raises(KeyError):
            reg.get("nonexistent")

    def test_list_tools(self) -> None:
        reg = create_default_registry()
        names = reg.list_tools()
        assert names == ["read_file", "sql_query", "vector_manage", "vector_search", "write_file"]

    def test_openai_definitions_format(self) -> None:
        reg = create_default_registry()
        defs = reg.get_openai_definitions()
        assert len(defs) == 5
        for d in defs:
            assert d["type"] == "function"
            func = d["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func


# ── validate_args tests ─────────────────────────────────────────────


class TestValidateArgs:
    def test_valid_args(self) -> None:
        tool = ReadFileTool()
        validate_args(tool, {"path": "/tmp/test.txt"})  # should not raise

    def test_invalid_args(self) -> None:
        tool = ReadFileTool()
        import jsonschema

        with pytest.raises(jsonschema.ValidationError):
            validate_args(tool, {"not_a_field": 123})


# ── sql_query tool tests ────────────────────────────────────────────


class TestSqlQueryTool:
    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> str:
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        conn.executemany("INSERT INTO t (val) VALUES (?)", [(f"row{i}",) for i in range(10)])
        conn.commit()
        conn.close()
        return str(db)

    @pytest.mark.asyncio
    async def test_valid_query(self, db_path: str) -> None:
        ctx = _make_ctx(sqlite_allow=[db_path])
        tool = SqlQueryTool()
        out = await tool.run(ctx, {"db_path": db_path, "query": "SELECT * FROM t"})
        assert out.success
        assert out.result["columns"] == ["id", "val"]
        assert len(out.result["rows"]) == 10
        assert out.result["truncated"] is False

    @pytest.mark.asyncio
    async def test_max_rows(self, db_path: str) -> None:
        ctx = _make_ctx(sqlite_allow=[db_path], max_rows=3)
        tool = SqlQueryTool()
        out = await tool.run(ctx, {"db_path": db_path, "query": "SELECT * FROM t"})
        assert out.success
        assert len(out.result["rows"]) == 3
        assert out.result["truncated"] is True

    @pytest.mark.asyncio
    async def test_disallowed_db_path(self, db_path: str) -> None:
        ctx = _make_ctx(sqlite_allow=["/some/other/path.db"])
        tool = SqlQueryTool()
        out = await tool.run(ctx, {"db_path": db_path, "query": "SELECT 1"})
        assert not out.success
        assert "not allowed" in out.error

    @pytest.mark.asyncio
    async def test_read_only_enforcement(self, db_path: str) -> None:
        ctx = _make_ctx(sqlite_allow=[db_path])
        tool = SqlQueryTool()
        out = await tool.run(ctx, {"db_path": db_path, "query": "INSERT INTO t (val) VALUES ('x')"})
        assert not out.success
        assert out.error  # sqlite read-only error


# ── read_file tool tests ────────────────────────────────────────────


class TestReadFileTool:
    @pytest.mark.asyncio
    async def test_valid_read(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        ctx = _make_ctx(fs_allow_read=[str(tmp_path)])
        tool = ReadFileTool()
        out = await tool.run(ctx, {"path": str(f)})
        assert out.success
        assert out.result == "hello world"

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_text("hello")
        ctx = _make_ctx(fs_allow_read=[str(tmp_path / "subdir")])
        tool = ReadFileTool()
        out = await tool.run(ctx, {"path": str(tmp_path / "subdir" / ".." / "hello.txt")})
        assert not out.success
        assert "not allowed" in out.error

    @pytest.mark.asyncio
    async def test_disallowed_prefix(self, tmp_path: Path) -> None:
        f = tmp_path / "secret.txt"
        f.write_text("secret")
        ctx = _make_ctx(fs_allow_read=["/some/other/prefix"])
        tool = ReadFileTool()
        out = await tool.run(ctx, {"path": str(f)})
        assert not out.success
        assert "not allowed" in out.error

    @pytest.mark.asyncio
    async def test_max_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("A" * 500)
        ctx = _make_ctx(fs_allow_read=[str(tmp_path)], max_bytes=10)
        tool = ReadFileTool()
        out = await tool.run(ctx, {"path": str(f)})
        assert out.success
        assert len(out.result) == 10


# ── write_file tool tests ───────────────────────────────────────────


class TestWriteFileTool:
    @pytest.mark.asyncio
    async def test_valid_write(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        ctx = _make_ctx(fs_allow_write=[str(tmp_path)])
        tool = WriteFileTool()
        out = await tool.run(ctx, {"path": str(target), "content": "written"})
        assert out.success
        assert target.read_text() == "written"

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        ctx = _make_ctx(fs_allow_write=[str(tmp_path / "subdir")])
        tool = WriteFileTool()
        out = await tool.run(ctx, {"path": str(tmp_path / "subdir" / ".." / "escape.txt"), "content": "x"})
        assert not out.success
        assert "not allowed" in out.error

    @pytest.mark.asyncio
    async def test_disallowed_prefix(self, tmp_path: Path) -> None:
        ctx = _make_ctx(fs_allow_write=["/some/other/prefix"])
        tool = WriteFileTool()
        out = await tool.run(ctx, {"path": "/tmp/nope.txt", "content": "x"})
        assert not out.success
        assert "not allowed" in out.error

    @pytest.mark.asyncio
    async def test_max_bytes(self, tmp_path: Path) -> None:
        target = tmp_path / "big.txt"
        ctx = _make_ctx(fs_allow_write=[str(tmp_path)], max_bytes=5)
        tool = WriteFileTool()
        out = await tool.run(ctx, {"path": str(target), "content": "A" * 100})
        assert not out.success
        assert "max_bytes" in out.error

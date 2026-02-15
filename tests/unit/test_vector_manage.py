"""Unit tests for the vector_manage tool."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from contracts.tool_sdk import ToolContext
from runtime.tools.vector_manage import VectorManageTool


# ── Helpers ─────────────────────────────────────────────────────────


def _make_ctx(
    *,
    vector_allow_write: list[str] | None = None,
) -> ToolContext:
    return ToolContext(
        request_id="test-req-1",
        manifest_data_paths={
            "vector_allow_write": vector_allow_write or [],
        },
    )


def _mock_embedding() -> AsyncMock:
    adapter = AsyncMock()
    adapter.embed.return_value = [[0.1, 0.2, 0.3]]
    return adapter


def _mock_vector_db() -> AsyncMock:
    adapter = AsyncMock()
    adapter.insert.return_value = ["id-1"]
    adapter.update.return_value = None
    adapter.delete.return_value = None
    return adapter


# ── Tests ───────────────────────────────────────────────────────────


class TestVectorManageTool:
    def test_definition(self) -> None:
        tool = VectorManageTool()
        defn = tool.definition()
        assert defn.name == "vector_manage"
        assert "data:vector_db_write" in defn.permissions

    # ── insert ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_insert_with_auto_embedding(self) -> None:
        emb = _mock_embedding()
        vec = _mock_vector_db()
        tool = VectorManageTool(embedding_adapter=emb, vector_adapter=vec)
        ctx = _make_ctx(vector_allow_write=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "operation": "insert",
            "documents": [{"text": "hello world"}],
        })

        assert output.success
        emb.embed.assert_called_once_with(["hello world"])
        vec.insert.assert_called_once()
        assert output.result["operation"] == "insert"
        assert output.result["count"] == 1

    @pytest.mark.asyncio
    async def test_insert_with_precomputed_embedding(self) -> None:
        emb = _mock_embedding()
        vec = _mock_vector_db()
        tool = VectorManageTool(embedding_adapter=emb, vector_adapter=vec)
        ctx = _make_ctx(vector_allow_write=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "operation": "insert",
            "documents": [{"text": "hello", "embedding": [0.5, 0.6]}],
        })

        assert output.success
        emb.embed.assert_not_called()
        vec.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_no_documents(self) -> None:
        tool = VectorManageTool(vector_adapter=_mock_vector_db())
        ctx = _make_ctx(vector_allow_write=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "operation": "insert",
            "documents": [],
        })

        assert not output.success
        assert "No documents" in output.error

    # ── update ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_update(self) -> None:
        emb = _mock_embedding()
        vec = _mock_vector_db()
        tool = VectorManageTool(embedding_adapter=emb, vector_adapter=vec)
        ctx = _make_ctx(vector_allow_write=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "operation": "update",
            "ids": ["id-1"],
            "documents": [{"text": "updated text"}],
        })

        assert output.success
        vec.update.assert_called_once()
        assert output.result["operation"] == "update"

    @pytest.mark.asyncio
    async def test_update_no_ids(self) -> None:
        tool = VectorManageTool(vector_adapter=_mock_vector_db())
        ctx = _make_ctx(vector_allow_write=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "operation": "update",
            "documents": [{"text": "x"}],
        })

        assert not output.success
        assert "No IDs" in output.error

    @pytest.mark.asyncio
    async def test_update_no_documents(self) -> None:
        tool = VectorManageTool(vector_adapter=_mock_vector_db())
        ctx = _make_ctx(vector_allow_write=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "operation": "update",
            "ids": ["id-1"],
        })

        assert not output.success
        assert "No documents" in output.error

    # ── delete ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        vec = _mock_vector_db()
        tool = VectorManageTool(vector_adapter=vec)
        ctx = _make_ctx(vector_allow_write=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "operation": "delete",
            "ids": ["id-1", "id-2"],
        })

        assert output.success
        vec.delete.assert_called_once_with("col", ["id-1", "id-2"])
        assert output.result["operation"] == "delete"
        assert output.result["count"] == 2

    @pytest.mark.asyncio
    async def test_delete_no_ids(self) -> None:
        tool = VectorManageTool(vector_adapter=_mock_vector_db())
        ctx = _make_ctx(vector_allow_write=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "operation": "delete",
        })

        assert not output.success
        assert "No IDs" in output.error

    # ── policy enforcement ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_write_not_allowed(self) -> None:
        tool = VectorManageTool(vector_adapter=_mock_vector_db())
        ctx = _make_ctx(vector_allow_write=["allowed_col"])

        output = await tool.run(ctx, {
            "collection": "forbidden_col",
            "operation": "insert",
            "documents": [{"text": "x"}],
        })

        assert not output.success
        assert "not allowed" in output.error

    @pytest.mark.asyncio
    async def test_write_glob_pattern(self) -> None:
        vec = _mock_vector_db()
        tool = VectorManageTool(vector_adapter=vec)
        ctx = _make_ctx(vector_allow_write=["data/*"])

        output = await tool.run(ctx, {
            "collection": "data/my_collection",
            "operation": "insert",
            "documents": [{"text": "x"}],
        })

        assert output.success

    # ── adapter not configured ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_no_vector_adapter(self) -> None:
        tool = VectorManageTool()
        ctx = _make_ctx(vector_allow_write=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "operation": "insert",
            "documents": [{"text": "x"}],
        })

        assert not output.success
        assert "not configured" in output.error

    @pytest.mark.asyncio
    async def test_unknown_operation(self) -> None:
        tool = VectorManageTool(vector_adapter=_mock_vector_db())
        ctx = _make_ctx(vector_allow_write=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "operation": "upsert",
        })

        assert not output.success
        assert "Unknown operation" in output.error

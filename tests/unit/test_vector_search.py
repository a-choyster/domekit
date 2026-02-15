"""Unit tests for the vector_search tool."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from contracts.tool_sdk import ToolContext
from contracts.vector_db import SearchResult
from runtime.tools.vector_search import VectorSearchTool


# ── Helpers ─────────────────────────────────────────────────────────


def _make_ctx(
    *,
    vector_allow: list[str] | None = None,
    default_top_k: int = 10,
) -> ToolContext:
    return ToolContext(
        request_id="test-req-1",
        manifest_data_paths={
            "vector_allow": vector_allow or [],
            "default_top_k": default_top_k,
        },
    )


def _mock_embedding() -> AsyncMock:
    adapter = AsyncMock()
    adapter.embed.return_value = [[0.1, 0.2, 0.3]]
    return adapter


def _mock_vector_db(results: list[SearchResult] | None = None) -> AsyncMock:
    adapter = AsyncMock()
    adapter.search.return_value = results or [
        SearchResult(id="doc-1", text="hello world", metadata={"tag": "test"}, score=0.95),
    ]
    return adapter


# ── Tests ───────────────────────────────────────────────────────────


class TestVectorSearchTool:
    def test_definition(self) -> None:
        tool = VectorSearchTool()
        defn = tool.definition()
        assert defn.name == "vector_search"
        assert "data:vector_db" in defn.permissions

    @pytest.mark.asyncio
    async def test_text_query_embeds_and_searches(self) -> None:
        emb = _mock_embedding()
        vec = _mock_vector_db()
        tool = VectorSearchTool(embedding_adapter=emb, vector_adapter=vec)
        ctx = _make_ctx(vector_allow=["my_collection"])

        output = await tool.run(ctx, {
            "collection": "my_collection",
            "query": "find similar docs",
        })

        assert output.success
        emb.embed.assert_called_once_with(["find similar docs"])
        vec.search.assert_called_once()
        assert output.result["count"] == 1

    @pytest.mark.asyncio
    async def test_raw_vector_search(self) -> None:
        vec = _mock_vector_db()
        tool = VectorSearchTool(vector_adapter=vec)
        ctx = _make_ctx(vector_allow=["my_collection"])

        output = await tool.run(ctx, {
            "collection": "my_collection",
            "query_vector": [0.1, 0.2, 0.3],
        })

        assert output.success
        vec.search.assert_called_once_with(
            collection="my_collection",
            query_vector=[0.1, 0.2, 0.3],
            top_k=10,
            filters=None,
        )

    @pytest.mark.asyncio
    async def test_collection_not_allowed(self) -> None:
        tool = VectorSearchTool(vector_adapter=_mock_vector_db())
        ctx = _make_ctx(vector_allow=["allowed_collection"])

        output = await tool.run(ctx, {
            "collection": "forbidden_collection",
            "query_vector": [0.1],
        })

        assert not output.success
        assert "not allowed" in output.error

    @pytest.mark.asyncio
    async def test_collection_glob_pattern(self) -> None:
        vec = _mock_vector_db()
        tool = VectorSearchTool(vector_adapter=vec)
        ctx = _make_ctx(vector_allow=["data/*"])

        output = await tool.run(ctx, {
            "collection": "data/knowledge_base",
            "query_vector": [0.1],
        })

        assert output.success

    @pytest.mark.asyncio
    async def test_no_query_or_vector_provided(self) -> None:
        tool = VectorSearchTool(vector_adapter=_mock_vector_db())
        ctx = _make_ctx(vector_allow=["col"])

        output = await tool.run(ctx, {"collection": "col"})

        assert not output.success
        assert "query" in output.error.lower() or "query_vector" in output.error.lower()

    @pytest.mark.asyncio
    async def test_text_query_without_embedding_adapter(self) -> None:
        tool = VectorSearchTool(vector_adapter=_mock_vector_db())
        ctx = _make_ctx(vector_allow=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "query": "some text",
        })

        assert not output.success
        assert "Embedding adapter not configured" in output.error

    @pytest.mark.asyncio
    async def test_no_vector_adapter(self) -> None:
        tool = VectorSearchTool()
        ctx = _make_ctx(vector_allow=["col"])

        output = await tool.run(ctx, {
            "collection": "col",
            "query_vector": [0.1],
        })

        assert not output.success
        assert "Vector database adapter not configured" in output.error

    @pytest.mark.asyncio
    async def test_top_k_from_args(self) -> None:
        vec = _mock_vector_db()
        tool = VectorSearchTool(vector_adapter=vec)
        ctx = _make_ctx(vector_allow=["col"])

        await tool.run(ctx, {
            "collection": "col",
            "query_vector": [0.1],
            "top_k": 5,
        })

        _, kwargs = vec.search.call_args
        assert kwargs["top_k"] == 5

    @pytest.mark.asyncio
    async def test_top_k_from_manifest_default(self) -> None:
        vec = _mock_vector_db()
        tool = VectorSearchTool(vector_adapter=vec)
        ctx = _make_ctx(vector_allow=["col"], default_top_k=20)

        await tool.run(ctx, {
            "collection": "col",
            "query_vector": [0.1],
        })

        _, kwargs = vec.search.call_args
        assert kwargs["top_k"] == 20

    @pytest.mark.asyncio
    async def test_filters_passed_through(self) -> None:
        vec = _mock_vector_db()
        tool = VectorSearchTool(vector_adapter=vec)
        ctx = _make_ctx(vector_allow=["col"])

        await tool.run(ctx, {
            "collection": "col",
            "query_vector": [0.1],
            "filters": {"tag": "important"},
        })

        _, kwargs = vec.search.call_args
        assert kwargs["filters"] == {"tag": "important"}

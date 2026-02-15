"""Built-in vector_search tool — similarity search against a local vector DB."""

from __future__ import annotations

import fnmatch
from typing import Any

from contracts.embedding import EmbeddingAdapter
from contracts.tool_sdk import BaseTool, ToolContext, ToolDefinition, ToolOutput
from contracts.vector_db import VectorDBAdapter


class VectorSearchTool(BaseTool):
    """Search a local vector database collection by semantic similarity."""

    def __init__(
        self,
        embedding_adapter: EmbeddingAdapter | None = None,
        vector_adapter: VectorDBAdapter | None = None,
    ) -> None:
        self._embedding = embedding_adapter
        self._vector = vector_adapter

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="vector_search",
            description="Search a local vector database collection by semantic similarity.",
            input_schema={
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Path to the vector collection.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Text to search for (auto-embedded).",
                    },
                    "query_vector": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Raw embedding vector (alternative to text query).",
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 10,
                        "description": "Number of results to return.",
                    },
                    "filters": {
                        "type": "object",
                        "description": "Metadata filters.",
                    },
                },
                "required": ["collection"],
                "additionalProperties": False,
            },
            permissions=["data:vector_db"],
        )

    async def run(self, ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
        collection = args["collection"]
        query = args.get("query")
        query_vector = args.get("query_vector")
        top_k = args.get("top_k", ctx.manifest_data_paths.get("default_top_k", 10))
        filters = args.get("filters")
        call_id = ctx.request_id

        # Validate collection path against manifest
        allowed: list[str] = ctx.manifest_data_paths.get("vector_allow", [])
        if not any(fnmatch.fnmatch(collection, pattern) for pattern in allowed):
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_search",
                error=f"Collection not allowed: {collection}",
                success=False,
            )

        # Must have either query text or query_vector
        if not query and not query_vector:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_search",
                error="Either 'query' or 'query_vector' must be provided.",
                success=False,
            )

        if self._vector is None:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_search",
                error="Vector database adapter not configured.",
                success=False,
            )

        # Convert text query to vector if needed
        if query and not query_vector:
            if self._embedding is None:
                return ToolOutput(
                    call_id=call_id,
                    tool_name="vector_search",
                    error="Embedding adapter not configured; provide query_vector instead.",
                    success=False,
                )
            try:
                vectors = await self._embedding.embed([query])
                query_vector = vectors[0]
            except Exception as exc:
                return ToolOutput(
                    call_id=call_id,
                    tool_name="vector_search",
                    error=f"Embedding failed: {exc}",
                    success=False,
                )

        try:
            results = await self._vector.search(
                collection=collection,
                query_vector=query_vector,
                top_k=top_k,
                filters=filters,
            )
        except Exception as exc:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_search",
                error=f"Search failed: {exc}",
                success=False,
            )

        return ToolOutput(
            call_id=call_id,
            tool_name="vector_search",
            result={
                "results": [r.model_dump() for r in results],
                "count": len(results),
            },
        )

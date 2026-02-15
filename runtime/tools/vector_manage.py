"""Built-in vector_manage tool — insert, update, delete in a local vector DB."""

from __future__ import annotations

import fnmatch
from typing import Any

from contracts.embedding import EmbeddingAdapter
from contracts.tool_sdk import BaseTool, ToolContext, ToolDefinition, ToolOutput
from contracts.vector_db import Document, VectorDBAdapter


class VectorManageTool(BaseTool):
    """Insert, update, or delete documents in a local vector database collection."""

    def __init__(
        self,
        embedding_adapter: EmbeddingAdapter | None = None,
        vector_adapter: VectorDBAdapter | None = None,
    ) -> None:
        self._embedding = embedding_adapter
        self._vector = vector_adapter

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="vector_manage",
            description=(
                "Insert, update, or delete documents in a local vector "
                "database collection."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Path to the vector collection.",
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["insert", "update", "delete"],
                        "description": "Operation to perform.",
                    },
                    "documents": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Documents with text and optional metadata.",
                    },
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Document IDs (for update/delete).",
                    },
                },
                "required": ["collection", "operation"],
                "additionalProperties": False,
            },
            permissions=["data:vector_db_write"],
        )

    async def run(self, ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
        collection = args["collection"]
        operation = args["operation"]
        raw_documents = args.get("documents", [])
        ids = args.get("ids", [])
        call_id = ctx.request_id

        # Validate collection path against manifest write policy
        allowed: list[str] = ctx.manifest_data_paths.get("vector_allow_write", [])
        if not any(fnmatch.fnmatch(collection, pattern) for pattern in allowed):
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_manage",
                error=f"Write not allowed for collection: {collection}",
                success=False,
            )

        if self._vector is None:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_manage",
                error="Vector database adapter not configured.",
                success=False,
            )

        if operation == "insert":
            return await self._handle_insert(call_id, collection, raw_documents)

        if operation == "update":
            return await self._handle_update(call_id, collection, ids, raw_documents)

        if operation == "delete":
            return await self._handle_delete(call_id, collection, ids)

        return ToolOutput(
            call_id=call_id,
            tool_name="vector_manage",
            error=f"Unknown operation: {operation}",
            success=False,
        )

    async def _auto_embed(self, documents: list[Document]) -> list[Document]:
        """Embed documents that don't already have embeddings."""
        if self._embedding is None:
            return documents

        texts_to_embed: list[str] = []
        indices: list[int] = []
        for i, doc in enumerate(documents):
            if doc.embedding is None:
                texts_to_embed.append(doc.text)
                indices.append(i)

        if not texts_to_embed:
            return documents

        embeddings = await self._embedding.embed(texts_to_embed)
        for idx, emb in zip(indices, embeddings):
            documents[idx] = documents[idx].model_copy(update={"embedding": emb})

        return documents

    async def _handle_insert(
        self, call_id: str, collection: str, raw_documents: list[dict],
    ) -> ToolOutput:
        if not raw_documents:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_manage",
                error="No documents provided for insert.",
                success=False,
            )

        documents = [Document(**d) for d in raw_documents]

        try:
            documents = await self._auto_embed(documents)
        except Exception as exc:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_manage",
                error=f"Embedding failed: {exc}",
                success=False,
            )

        try:
            inserted_ids = await self._vector.insert(collection, documents)
        except Exception as exc:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_manage",
                error=f"Insert failed: {exc}",
                success=False,
            )

        return ToolOutput(
            call_id=call_id,
            tool_name="vector_manage",
            result={"operation": "insert", "ids": inserted_ids, "count": len(inserted_ids)},
        )

    async def _handle_update(
        self, call_id: str, collection: str, ids: list[str], raw_documents: list[dict],
    ) -> ToolOutput:
        if not ids:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_manage",
                error="No IDs provided for update.",
                success=False,
            )
        if not raw_documents:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_manage",
                error="No documents provided for update.",
                success=False,
            )

        documents = [Document(**d) for d in raw_documents]

        try:
            documents = await self._auto_embed(documents)
        except Exception as exc:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_manage",
                error=f"Embedding failed: {exc}",
                success=False,
            )

        try:
            await self._vector.update(collection, ids, documents)
        except Exception as exc:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_manage",
                error=f"Update failed: {exc}",
                success=False,
            )

        return ToolOutput(
            call_id=call_id,
            tool_name="vector_manage",
            result={"operation": "update", "ids": ids, "count": len(ids)},
        )

    async def _handle_delete(
        self, call_id: str, collection: str, ids: list[str],
    ) -> ToolOutput:
        if not ids:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_manage",
                error="No IDs provided for delete.",
                success=False,
            )

        try:
            await self._vector.delete(collection, ids)
        except Exception as exc:
            return ToolOutput(
                call_id=call_id,
                tool_name="vector_manage",
                error=f"Delete failed: {exc}",
                success=False,
            )

        return ToolOutput(
            call_id=call_id,
            tool_name="vector_manage",
            result={"operation": "delete", "ids": ids, "count": len(ids)},
        )

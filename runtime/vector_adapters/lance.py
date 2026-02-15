"""LanceDB vector adapter.

Wraps lancedb for local embedded vector storage with Lance columnar format.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import lancedb

from contracts.vector_db import Document, SearchResult, VectorDBAdapter


class LanceVectorAdapter(VectorDBAdapter):
    """Vector adapter backed by LanceDB with on-disk Lance tables."""

    def __init__(self, db_path: str) -> None:
        self._db = lancedb.connect(db_path)

    # ── search ────────────────────────────────────────────────────────

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        def _search() -> list[SearchResult]:
            table = self._db.open_table(collection)
            query = table.search(query_vector).limit(top_k)
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if isinstance(value, str):
                        where_clauses.append(f"{key} = '{value}'")
                    else:
                        where_clauses.append(f"{key} = {value}")
                query = query.where(" AND ".join(where_clauses))
            rows = query.to_list()
            results: list[SearchResult] = []
            for row in rows:
                distance = row.get("_distance", 0.0)
                metadata_raw = row.get("metadata", "{}")
                if isinstance(metadata_raw, str):
                    metadata = json.loads(metadata_raw)
                else:
                    metadata = metadata_raw
                results.append(
                    SearchResult(
                        id=row["id"],
                        text=row["text"],
                        metadata=metadata,
                        score=1.0 / (1.0 + distance),
                    )
                )
            return results

        return await asyncio.to_thread(_search)

    # ── insert ────────────────────────────────────────────────────────

    async def insert(
        self, collection: str, documents: list[Document]
    ) -> list[str]:
        def _insert() -> list[str]:
            ids: list[str] = []
            data: list[dict[str, Any]] = []
            for doc in documents:
                doc_id = doc.id or str(uuid.uuid4())
                ids.append(doc_id)
                row: dict[str, Any] = {
                    "id": doc_id,
                    "text": doc.text,
                    "metadata": json.dumps(doc.metadata),
                }
                if doc.embedding is not None:
                    row["vector"] = doc.embedding
                data.append(row)

            table_names = self._db.table_names()
            if collection in table_names:
                table = self._db.open_table(collection)
                table.add(data)
            else:
                self._db.create_table(collection, data)
            return ids

        return await asyncio.to_thread(_insert)

    # ── update ────────────────────────────────────────────────────────

    async def update(
        self, collection: str, ids: list[str], documents: list[Document]
    ) -> None:
        def _update() -> None:
            table = self._db.open_table(collection)
            for doc_id, doc in zip(ids, documents):
                # LanceDB lacks row-level update; delete and re-insert
                table.delete(f"id = '{doc_id}'")
                row: dict[str, Any] = {
                    "id": doc_id,
                    "text": doc.text,
                    "metadata": json.dumps(doc.metadata),
                }
                if doc.embedding is not None:
                    row["vector"] = doc.embedding
                table.add([row])

        await asyncio.to_thread(_update)

    # ── delete ────────────────────────────────────────────────────────

    async def delete(self, collection: str, ids: list[str]) -> None:
        def _delete() -> None:
            table = self._db.open_table(collection)
            formatted_ids = ", ".join(f"'{i}'" for i in ids)
            table.delete(f"id IN ({formatted_ids})")

        await asyncio.to_thread(_delete)

    # ── list_collections ──────────────────────────────────────────────

    async def list_collections(self) -> list[str]:
        def _list() -> list[str]:
            return self._db.table_names()

        return await asyncio.to_thread(_list)

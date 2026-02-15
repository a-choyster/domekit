"""ChromaDB vector adapter.

Wraps chromadb.PersistentClient for local persistent vector storage.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import chromadb

from contracts.vector_db import Document, SearchResult, VectorDBAdapter


class ChromaVectorAdapter(VectorDBAdapter):
    """Vector adapter backed by ChromaDB with on-disk persistence."""

    def __init__(self, persist_path: str) -> None:
        self._client = chromadb.PersistentClient(path=persist_path)

    def _get_or_create_collection(self, name: str) -> chromadb.Collection:
        return self._client.get_or_create_collection(name=name)

    # ── search ────────────────────────────────────────────────────────

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        def _search() -> list[SearchResult]:
            col = self._get_or_create_collection(collection)
            result = col.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=filters or None,
            )
            results: list[SearchResult] = []
            ids = result.get("ids", [[]])[0]
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            for i, doc_id in enumerate(ids):
                distance = distances[i] if i < len(distances) else 0.0
                results.append(
                    SearchResult(
                        id=doc_id,
                        text=documents[i] if i < len(documents) else "",
                        metadata=metadatas[i] if i < len(metadatas) else {},
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
            col = self._get_or_create_collection(collection)
            ids: list[str] = []
            texts: list[str] = []
            metadatas: list[dict[str, Any]] = []
            embeddings: list[list[float]] = []
            has_embeddings = False

            for doc in documents:
                doc_id = doc.id or str(uuid.uuid4())
                ids.append(doc_id)
                texts.append(doc.text)
                metadatas.append(doc.metadata)
                if doc.embedding is not None:
                    embeddings.append(doc.embedding)
                    has_embeddings = True

            col.add(
                ids=ids,
                documents=texts,
                embeddings=embeddings if has_embeddings else None,
                metadatas=metadatas,
            )
            return ids

        return await asyncio.to_thread(_insert)

    # ── update ────────────────────────────────────────────────────────

    async def update(
        self, collection: str, ids: list[str], documents: list[Document]
    ) -> None:
        def _update() -> None:
            col = self._get_or_create_collection(collection)
            texts: list[str] = []
            metadatas: list[dict[str, Any]] = []
            embeddings: list[list[float]] = []
            has_embeddings = False

            for doc in documents:
                texts.append(doc.text)
                metadatas.append(doc.metadata)
                if doc.embedding is not None:
                    embeddings.append(doc.embedding)
                    has_embeddings = True

            col.update(
                ids=ids,
                documents=texts,
                embeddings=embeddings if has_embeddings else None,
                metadatas=metadatas,
            )

        await asyncio.to_thread(_update)

    # ── delete ────────────────────────────────────────────────────────

    async def delete(self, collection: str, ids: list[str]) -> None:
        def _delete() -> None:
            col = self._get_or_create_collection(collection)
            col.delete(ids=ids)

        await asyncio.to_thread(_delete)

    # ── list_collections ──────────────────────────────────────────────

    async def list_collections(self) -> list[str]:
        def _list() -> list[str]:
            return [c.name for c in self._client.list_collections()]

        return await asyncio.to_thread(_list)

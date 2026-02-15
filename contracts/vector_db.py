"""Vector database adapter contracts.

Defines the abstract interface for local vector database backends
and the shared data models for documents and search results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


# ── Data models ──────────────────────────────────────────────────────


class Document(BaseModel):
    """A document to store in a vector collection."""

    id: str | None = None
    text: str
    metadata: dict[str, Any] = {}
    embedding: list[float] | None = None


class SearchResult(BaseModel):
    """A single result from a similarity search."""

    id: str
    text: str
    metadata: dict[str, Any] = {}
    score: float


# ── Abstract adapter ─────────────────────────────────────────────────


class VectorDBAdapter(ABC):
    """Abstract base class for local vector database backends."""

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search a collection by vector similarity."""
        ...

    @abstractmethod
    async def insert(
        self, collection: str, documents: list[Document]
    ) -> list[str]:
        """Insert documents into a collection. Returns assigned IDs."""
        ...

    @abstractmethod
    async def update(
        self, collection: str, ids: list[str], documents: list[Document]
    ) -> None:
        """Update existing documents by ID."""
        ...

    @abstractmethod
    async def delete(self, collection: str, ids: list[str]) -> None:
        """Delete documents by ID."""
        ...

    @abstractmethod
    async def list_collections(self) -> list[str]:
        """List all available collections."""
        ...

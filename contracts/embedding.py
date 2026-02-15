"""Embedding adapter contracts.

Defines the abstract interface for embedding generation backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class EmbeddingResult(BaseModel):
    """Result from an embedding operation."""

    embeddings: list[list[float]]
    model: str


class EmbeddingAdapter(ABC):
    """Abstract base class for embedding generation backends."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return the name of the embedding model."""
        ...

"""Ollama embedding adapter.

Proxies embedding requests to a local Ollama instance via httpx.
"""

from __future__ import annotations

import httpx

from contracts.embedding import EmbeddingAdapter


class OllamaEmbeddingAdapter(EmbeddingAdapter):
    """Async adapter for the Ollama /api/embed endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts via Ollama."""
        payload = {"model": self._model, "input": texts}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._base_url}/api/embed", json=payload
                )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self._base_url}: {exc}"
            ) from exc

        if resp.status_code != 200:
            raise RuntimeError(
                f"Ollama embed request failed ({resp.status_code}): {resp.text}"
            )

        data = resp.json()
        return data["embeddings"]

    def model_name(self) -> str:
        """Return the name of the embedding model."""
        return self._model

"""Unit tests for the Ollama embedding adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runtime.embedding_adapters.ollama import OllamaEmbeddingAdapter


class TestOllamaEmbeddingAdapter:
    def test_model_name(self) -> None:
        adapter = OllamaEmbeddingAdapter(model="test-model")
        assert adapter.model_name() == "test-model"

    def test_default_model(self) -> None:
        adapter = OllamaEmbeddingAdapter()
        assert adapter.model_name() == "nomic-embed-text"

    @pytest.mark.asyncio
    async def test_embed_single_text(self) -> None:
        adapter = OllamaEmbeddingAdapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embeddings": [[0.1, 0.2, 0.3]],
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runtime.embedding_adapters.ollama.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.embed(["hello world"])

        assert result == [[0.1, 0.2, 0.3]]
        mock_client.post.assert_called_once_with(
            "http://localhost:11434/api/embed",
            json={"model": "nomic-embed-text", "input": ["hello world"]},
        )

    @pytest.mark.asyncio
    async def test_embed_multiple_texts(self) -> None:
        adapter = OllamaEmbeddingAdapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embeddings": [[0.1, 0.2], [0.3, 0.4]],
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runtime.embedding_adapters.ollama.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.embed(["text1", "text2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]

    @pytest.mark.asyncio
    async def test_embed_connection_error(self) -> None:
        import httpx

        adapter = OllamaEmbeddingAdapter()
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runtime.embedding_adapters.ollama.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
                await adapter.embed(["hello"])

    @pytest.mark.asyncio
    async def test_embed_non_200_response(self) -> None:
        adapter = OllamaEmbeddingAdapter()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "model not found"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runtime.embedding_adapters.ollama.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="Ollama embed request failed"):
                await adapter.embed(["hello"])

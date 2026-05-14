"""Async embedding adapters for OpenAI-compatible and Ollama APIs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class EmbeddingConfig:
    api_format: str = "openai_compat"
    base_url: str = ""
    model: str = ""
    api_key: str = ""


class BaseEmbeddingAdapter(ABC):
    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        ...


class OpenAICompatEmbeddingAdapter(BaseEmbeddingAdapter):
    """Covers OpenAI, DeepSeek, SiliconFlow, LM Studio — all use /v1/embeddings."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    def _endpoint(self) -> str:
        base = self._base_url
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return f"{base}/embeddings"

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        all_embeddings: list[list[float]] = []
        batch_size = 100
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                resp = await client.post(
                    self._endpoint(),
                    headers=self._headers(),
                    json={"input": batch, "model": self._model},
                )
                resp.raise_for_status()
                data = resp.json()["data"]
                data.sort(key=lambda x: x["index"])
                all_embeddings.extend(item["embedding"] for item in data)
        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        results = await self.embed_documents([query])
        return results[0]


class OllamaEmbeddingAdapter(BaseEmbeddingAdapter):
    """Ollama uses /api/embeddings with different request/response format."""

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def _endpoint(self) -> str:
        return f"{self._base_url}/api/embeddings"

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings: list[list[float]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                resp = await client.post(
                    self._endpoint(),
                    json={"model": self._model, "prompt": text},
                )
                resp.raise_for_status()
                embeddings.append(resp.json()["embedding"])
        return embeddings

    async def embed_query(self, query: str) -> list[float]:
        results = await self.embed_documents([query])
        return results[0]


def create_embedding_adapter(config: EmbeddingConfig) -> BaseEmbeddingAdapter:
    """Factory function keyed by config.api_format."""
    if config.api_format == "ollama":
        return OllamaEmbeddingAdapter(base_url=config.base_url, model=config.model)
    return OpenAICompatEmbeddingAdapter(
        api_key=config.api_key, base_url=config.base_url, model=config.model
    )

from __future__ import annotations

import httpx

from rag_document_processor.application.ports.embedding_pipeline import IEmbedder


class JinaEmbedder(IEmbedder):
    name = "jina"

    def __init__(self, *, api_key: str, model: str, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client

    async def embed_texts(
        self,
        texts: list[str],
        *,
        late_chunking: bool = False,
        dimensions: int | None = None,
    ) -> list[tuple[float, ...]]:
        if not texts:
            return []
        payload: dict = {"model": self._model, "input": texts, "late_chunking": late_chunking}
        if dimensions is not None:
            payload["dimensions"] = dimensions
        resp = await self._client.post(
            "https://api.jina.ai/v1/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
        return [tuple(float(x) for x in item["embedding"]) for item in items]

from __future__ import annotations

from openai import AsyncOpenAI

from rag_document_processor.application.ports.embedding_pipeline import IEmbedder


class OpenAIEmbedder(IEmbedder):
    name = "openai"

    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def embed_texts(
        self,
        texts: list[str],
        *,
        late_chunking: bool = False,
        dimensions: int | None = None,
    ) -> list[tuple[float, ...]]:
        if late_chunking:
            raise ValueError("OpenAI embedder does not support late_chunking")
        if not texts:
            return []
        kwargs: dict = {"model": self._model, "input": texts}
        if dimensions is not None:
            kwargs["dimensions"] = dimensions
        resp = await self._client.embeddings.create(**kwargs)
        items = sorted(resp.data, key=lambda d: d.index)
        return [tuple(float(x) for x in item.embedding) for item in items]

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from rag_document_processor.domain.value_objects.embedded_chunk import EmbeddedChunk


class IMacroSplitter(Protocol):
    """Splits long documents into macro blocks that fit the embedder context window."""

    name: str

    async def split(self, text: str) -> AsyncIterator[str]: ...


class IChunker(Protocol):
    """Classic chunk-then-embed: splits text into smaller segments."""

    name: str

    async def chunk(self, text: str) -> AsyncIterator[str]: ...


class IEmbedder(Protocol):
    name: str

    async def embed_texts(
        self,
        texts: list[str],
        *,
        late_chunking: bool = False,
        dimensions: int | None = None,
    ) -> list[tuple[float, ...]]:
        """Return one embedding vector per input text (same order)."""


class IEmbeddingPipeline(Protocol):
    name: str

    async def process(
        self,
        text: str,
        *,
        metadata: dict[str, Any],
        embedding_dimensions: int | None = None,
    ) -> AsyncIterator[EmbeddedChunk]: ...

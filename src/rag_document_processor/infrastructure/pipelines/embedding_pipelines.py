from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

from rag_document_processor.application.ports.embedding_pipeline import IEmbedder, IEmbeddingPipeline, IMacroSplitter
from rag_document_processor.domain.value_objects.embedded_chunk import EmbeddedChunk


def _sentences(block: str) -> list[str]:
    text = block.strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    out = [p.strip() for p in parts if p.strip()]
    if not out:
        return [text]
    return out


class LateChunkingPipeline(IEmbeddingPipeline):
    name = "late_chunking"

    def __init__(self, macro_splitter: IMacroSplitter, embedder: IEmbedder) -> None:
        self._macro = macro_splitter
        self._embedder = embedder

    async def process(self, text: str, *, metadata: dict[str, Any]) -> AsyncIterator[EmbeddedChunk]:
        macro_idx = 0
        async for block in self._macro.split(text):
            sents = _sentences(block)
            if not sents:
                macro_idx += 1
                continue
            vectors = await self._embedder.embed_texts(sents, late_chunking=True)
            for i, (sent, vec) in enumerate(zip(sents, vectors, strict=True)):
                yield EmbeddedChunk(
                    sent,
                    vec,
                    {**metadata, "macro_index": macro_idx, "sentence_index": i, "pipeline": self.name},
                )
            macro_idx += 1


class ChunkThenEmbedPipeline(IEmbeddingPipeline):
    name = "chunk_then_embed"

    def __init__(self, chunker, embedder: IEmbedder) -> None:
        from rag_document_processor.application.ports.embedding_pipeline import IChunker

        self._chunker: IChunker = chunker
        self._embedder = embedder

    async def process(self, text: str, *, metadata: dict[str, Any]) -> AsyncIterator[EmbeddedChunk]:
        idx = 0
        async for seg in self._chunker.chunk(text):
            vectors = await self._embedder.embed_texts([seg], late_chunking=False)
            yield EmbeddedChunk(seg, vectors[0], {**metadata, "chunk_index": idx, "pipeline": self.name})
            idx += 1

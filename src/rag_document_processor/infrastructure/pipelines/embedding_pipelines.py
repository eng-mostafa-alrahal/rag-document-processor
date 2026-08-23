from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from rag_document_processor.application.ports.embedding_pipeline import IEmbedder, IEmbeddingPipeline, IMacroSplitter
from rag_document_processor.domain.value_objects.embedded_chunk import EmbeddedChunk
from rag_document_processor.infrastructure.pipelines.late_chunk_enhancer import (
    TokenCounter,
    _dedupe_adjacent,
    batch_chunks,
    enhance_chunks,
    simple_token_count,
)


class LateChunkingPipeline(IEmbeddingPipeline):
    """Late chunking with macro split → enhance → batch → Jina.

    Flow: macro splitter produces chunk text (recursive / token_aware / semantic,
    with optional overlap) → ENHANCE enforces ``min_tokens``..``max_tokens`` →
    BATCH packs under the Jina request budget → one ``late_chunking=true`` call
    per batch so vectors share context.
    """

    name = "late_chunking"

    def __init__(
        self,
        macro_splitter: IMacroSplitter,
        embedder: IEmbedder,
        *,
        min_tokens: int = 256,
        max_tokens: int = 512,
        batch_tokens: int = 7000,
        count_tokens: TokenCounter = simple_token_count,
    ) -> None:
        self._macro = macro_splitter
        self._embedder = embedder
        self._min_tokens = min_tokens
        self._max_tokens = max_tokens
        self._batch_tokens = batch_tokens
        self._count_tokens = count_tokens

    async def process(
        self,
        text: str,
        *,
        metadata: dict[str, Any],
        embedding_dimensions: int | None = None,
    ) -> AsyncIterator[EmbeddedChunk]:
        meta = {**metadata}
        if embedding_dimensions is not None:
            meta["embedding_dimensions"] = embedding_dimensions

        # 1. Macro split: each yielded block is one chunk candidate (may overlap).
        macro_chunks: list[str] = []
        async for block in self._macro.split(text):
            if block.strip():
                macro_chunks.append(block.strip())
        macro_chunks = _dedupe_adjacent(macro_chunks)
        if not macro_chunks:
            return

        # 2. ENHANCE: enforce min/max token bounds on macro output.
        chunks = enhance_chunks(
            macro_chunks,
            min_tokens=self._min_tokens,
            max_tokens=self._max_tokens,
            count_tokens=self._count_tokens,
        )
        if not chunks:
            return

        # 3. BATCH: pack chunks under the per-request token budget.
        batches = batch_chunks(
            chunks,
            max_batch_tokens=self._batch_tokens,
            count_tokens=self._count_tokens,
        )

        # 4. EMBED: one late_chunking request per batch; yield one chunk per item.
        chunk_idx = 0
        for batch_idx, batch in enumerate(batches):
            vectors = await self._embedder.embed_texts(
                batch, late_chunking=True, dimensions=embedding_dimensions
            )
            for chunk_text, vec in zip(batch, vectors, strict=True):
                yield EmbeddedChunk(
                    chunk_text,
                    vec,
                    {
                        **meta,
                        "chunk_index": chunk_idx,
                        "batch_index": batch_idx,
                        "token_count": self._count_tokens(chunk_text),
                        "pipeline": self.name,
                    },
                )
                chunk_idx += 1


class ChunkThenEmbedPipeline(IEmbeddingPipeline):
    name = "chunk_then_embed"

    def __init__(self, chunker, embedder: IEmbedder) -> None:
        from rag_document_processor.application.ports.embedding_pipeline import IChunker

        self._chunker: IChunker = chunker
        self._embedder = embedder

    async def process(
        self,
        text: str,
        *,
        metadata: dict[str, Any],
        embedding_dimensions: int | None = None,
    ) -> AsyncIterator[EmbeddedChunk]:
        idx = 0
        meta = {**metadata}
        if embedding_dimensions is not None:
            meta["embedding_dimensions"] = embedding_dimensions
        async for seg in self._chunker.chunk(text):
            vectors = await self._embedder.embed_texts(
                [seg], late_chunking=False, dimensions=embedding_dimensions
            )
            yield EmbeddedChunk(seg, vectors[0], {**meta, "chunk_index": idx, "pipeline": self.name})
            idx += 1

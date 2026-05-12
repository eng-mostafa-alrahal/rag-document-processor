from __future__ import annotations

import pytest

from rag_document_processor.application.ports.embedding_pipeline import IEmbedder, IEmbeddingPipeline
from rag_document_processor.infrastructure.pipelines.embedding_pipelines import LateChunkingPipeline
from rag_document_processor.infrastructure.splitters.macro_splitters import RecursiveMacroSplitter


class FakeEmbedder(IEmbedder):
    name = "fake"

    async def embed_texts(self, texts: list[str], *, late_chunking: bool = False) -> list[tuple[float, ...]]:
        return [tuple(float(i + 1) for _ in range(4)) for i, _ in enumerate(texts)]


@pytest.mark.asyncio
async def test_late_chunking_pipeline_emits_chunks() -> None:
    macro = RecursiveMacroSplitter(chunk_size=10_000, chunk_overlap=0)
    pipe: IEmbeddingPipeline = LateChunkingPipeline(macro_splitter=macro, embedder=FakeEmbedder())
    out = [c async for c in pipe.process("A. B. C.", metadata={"k": "v"})]
    assert len(out) == 3
    assert all(isinstance(x.embedding, tuple) for x in out)

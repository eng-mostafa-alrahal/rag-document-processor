from __future__ import annotations

import pytest

from rag_document_processor.application.ports.embedding_pipeline import IEmbedder, IEmbeddingPipeline
from rag_document_processor.infrastructure.pipelines.embedding_pipelines import LateChunkingPipeline
from rag_document_processor.infrastructure.pipelines.late_chunk_enhancer import simple_token_count
from rag_document_processor.infrastructure.splitters.macro_splitters import RecursiveMacroSplitter


class FakeEmbedder(IEmbedder):
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def embed_texts(
        self,
        texts: list[str],
        *,
        late_chunking: bool = False,
        dimensions: int | None = None,
    ) -> list[tuple[float, ...]]:
        self.calls.append({"texts": list(texts), "late_chunking": late_chunking, "dimensions": dimensions})
        return [tuple(float(i + 1) for _ in range(4)) for i, _ in enumerate(texts)]


@pytest.mark.asyncio
async def test_late_chunking_merges_tiny_fragments() -> None:
    macro = RecursiveMacroSplitter(chunk_size=10_000, chunk_overlap=0)
    embedder = FakeEmbedder()
    pipe: IEmbeddingPipeline = LateChunkingPipeline(
        macro_splitter=macro,
        embedder=embedder,
        min_tokens=1,
        max_tokens=4,
        batch_tokens=1000,
        count_tokens=simple_token_count,
    )
    text = "Alpha one. Beta two. Gamma three. Delta four."
    out = [c async for c in pipe.process(text, metadata={"k": "v"})]

    # Four 2-word sentences merge into two 4-word chunks instead of four.
    assert len(out) == 2
    assert all(c.metadata["pipeline"] == "late_chunking" for c in out)
    assert [c.metadata["chunk_index"] for c in out] == [0, 1]
    assert all("token_count" in c.metadata for c in out)


@pytest.mark.asyncio
async def test_late_chunking_uses_late_flag_and_batches() -> None:
    macro = RecursiveMacroSplitter(chunk_size=10_000, chunk_overlap=0)
    embedder = FakeEmbedder()
    pipe = LateChunkingPipeline(
        macro_splitter=macro,
        embedder=embedder,
        min_tokens=1,
        max_tokens=2,
        batch_tokens=4,  # ~2 chunks (2 words each) per batch
        count_tokens=simple_token_count,
    )
    text = "aa bb. cc dd. ee ff. gg hh."
    out = [c async for c in pipe.process(text, metadata={})]

    assert len(out) == 4
    # late_chunking must be requested on every batch (otherwise it's meaningless).
    assert embedder.calls, "embedder was never called"
    assert all(call["late_chunking"] is True for call in embedder.calls)
    # Multiple batches => shared-context requests, not one-per-chunk.
    assert len(embedder.calls) >= 2
    assert {c.metadata["batch_index"] for c in out} == {0, 1}

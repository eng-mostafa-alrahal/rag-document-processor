from __future__ import annotations

import pytest

from rag_document_processor.infrastructure.pipelines.embedding_pipelines import _sentences


def test_sentences_splits_on_period() -> None:
    s = "Hello world. Next sentence! And another?"
    parts = _sentences(s)
    assert len(parts) == 3


@pytest.mark.asyncio
async def test_recursive_macro_splitter_yields_parts() -> None:
    from rag_document_processor.infrastructure.splitters.macro_splitters import RecursiveMacroSplitter

    splitter = RecursiveMacroSplitter(chunk_size=200, chunk_overlap=20)
    text = "paragraph one\n\n" + ("word " * 200)
    parts = [p async for p in splitter.split(text)]
    assert len(parts) >= 1

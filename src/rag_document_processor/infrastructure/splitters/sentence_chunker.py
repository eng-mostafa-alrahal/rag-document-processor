from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from llama_index.core import Document as LIDocument
from llama_index.core.node_parser import SentenceSplitter

from rag_document_processor.application.ports.embedding_pipeline import IChunker


class RecursiveSentenceChunker(IChunker):
    name = "recursive_sentence"

    def __init__(self, *, chunk_size: int = 1500, chunk_overlap: int = 150) -> None:
        self._splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    async def chunk(self, text: str) -> AsyncIterator[str]:
        def _run() -> list[str]:
            nodes = self._splitter.get_nodes_from_documents([LIDocument(text=text)])
            return [n.get_content(metadata_mode="none") for n in nodes]

        parts = await asyncio.to_thread(_run)
        for p in parts:
            if p.strip():
                yield p.strip()

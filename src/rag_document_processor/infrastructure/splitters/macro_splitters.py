from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from llama_index.core import Document as LIDocument
from llama_index.core.node_parser import SentenceSplitter

from rag_document_processor.application.ports.embedding_pipeline import IMacroSplitter


class RecursiveMacroSplitter(IMacroSplitter):
    name = "recursive"

    def __init__(self, *, chunk_size: int = 6000, chunk_overlap: int = 400) -> None:
        self._splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    async def split(self, text: str) -> AsyncIterator[str]:
        def _run() -> list[str]:
            nodes = self._splitter.get_nodes_from_documents([LIDocument(text=text)])
            return [n.get_content(metadata_mode="none") for n in nodes]

        parts = await asyncio.to_thread(_run)
        for p in parts:
            if p.strip():
                yield p.strip()


class TokenAwareMacroSplitter(IMacroSplitter):
    name = "token_aware"

    def __init__(self, *, model: str = "gpt-4o-mini", max_tokens: int = 8192, overlap_tokens: int = 128) -> None:
        import tiktoken

        try:
            self._enc = tiktoken.encoding_for_model(model)
        except KeyError:
            self._enc = tiktoken.get_encoding("cl100k_base")
        self._max = max_tokens
        self._overlap = overlap_tokens

    async def split(self, text: str) -> AsyncIterator[str]:
        tokens = self._enc.encode(text)
        if not tokens:
            return
        start = 0
        while start < len(tokens):
            end = min(start + self._max, len(tokens))
            piece = self._enc.decode(tokens[start:end])
            if piece.strip():
                yield piece.strip()
            if end >= len(tokens):
                break
            start = max(end - self._overlap, start + 1)


class SemanticMacroSplitter(IMacroSplitter):
    name = "semantic"

    def __init__(self, *, openai_api_key: str, buffer_size: int = 1, breakpoint_percentile_threshold: int = 95) -> None:
        from llama_index.core.node_parser import SemanticSplitterNodeParser
        from llama_index.embeddings.openai import OpenAIEmbedding

        embed = OpenAIEmbedding(api_key=openai_api_key, model="text-embedding-3-small")
        self._parser = SemanticSplitterNodeParser(
            buffer_size=buffer_size,
            breakpoint_percentile_threshold=breakpoint_percentile_threshold,
            embed_model=embed,
        )

    async def split(self, text: str) -> AsyncIterator[str]:
        def _run() -> list[str]:
            nodes = self._parser.get_nodes_from_documents([LIDocument(text=text)])
            return [n.get_content(metadata_mode="none") for n in nodes]

        parts = await asyncio.to_thread(_run)
        for p in parts:
            if p.strip():
                yield p.strip()

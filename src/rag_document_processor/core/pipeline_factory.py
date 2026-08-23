from __future__ import annotations

import httpx

from rag_document_processor.application.ports.embedding_pipeline import IEmbeddingPipeline, IMacroSplitter
from rag_document_processor.core.config import Settings
from rag_document_processor.core.ingest_embedding_options import MacroKind, ResolvedIngestEmbeddingOptions
from rag_document_processor.infrastructure.embedders.jina_embedder import JinaEmbedder
from rag_document_processor.infrastructure.embedders.openai_embedder import OpenAIEmbedder
from rag_document_processor.infrastructure.pipelines.embedding_pipelines import ChunkThenEmbedPipeline, LateChunkingPipeline
from rag_document_processor.infrastructure.pipelines.late_chunk_enhancer import chars_for_tokens, make_token_counter
from rag_document_processor.infrastructure.splitters.macro_splitters import (
    RecursiveMacroSplitter,
    SemanticMacroSplitter,
    TokenAwareMacroSplitter,
)
from rag_document_processor.infrastructure.splitters.sentence_chunker import RecursiveSentenceChunker

# Small overlap between consecutive macro chunks (late_chunking only).
DEFAULT_MACRO_OVERLAP_TOKENS = 128


def build_macro_splitter(
    settings: Settings,
    macro: MacroKind,
    *,
    max_tokens: int,
    overlap_tokens: int = DEFAULT_MACRO_OVERLAP_TOKENS,
) -> IMacroSplitter:
    """Build a macro splitter sized for late-chunking chunk candidates."""
    if macro == "semantic":
        if not settings.openai_api_key:
            return RecursiveMacroSplitter(
                chunk_size=chars_for_tokens(max_tokens),
                chunk_overlap=chars_for_tokens(overlap_tokens),
            )
        return SemanticMacroSplitter(openai_api_key=settings.openai_api_key)
    if macro == "token_aware":
        return TokenAwareMacroSplitter(max_tokens=max_tokens, overlap_tokens=overlap_tokens)
    return RecursiveMacroSplitter(
        chunk_size=chars_for_tokens(max_tokens),
        chunk_overlap=chars_for_tokens(overlap_tokens),
    )


def build_embedding_pipeline(
    settings: Settings,
    httpx_client: httpx.AsyncClient,
    resolved: ResolvedIngestEmbeddingOptions,
) -> IEmbeddingPipeline:
    if resolved.embedding_pipeline == "late_chunking":
        macro = build_macro_splitter(
            settings,
            resolved.macro_splitter,
            max_tokens=resolved.late_chunk_max_tokens,
            overlap_tokens=DEFAULT_MACRO_OVERLAP_TOKENS,
        )
        embedder = JinaEmbedder(
            api_key=settings.jina_api_key or "",
            model=resolved.jina_embedding_model,
            client=httpx_client,
        )
        return LateChunkingPipeline(
            macro_splitter=macro,
            embedder=embedder,
            min_tokens=resolved.late_chunk_min_tokens,
            max_tokens=resolved.late_chunk_max_tokens,
            batch_tokens=resolved.late_chunk_batch_tokens,
            count_tokens=make_token_counter(),
        )
    chunker = RecursiveSentenceChunker()
    if resolved.embedder == "openai":
        embedder = OpenAIEmbedder(
            api_key=settings.openai_api_key or "",
            model=resolved.openai_embedding_model,
        )
    else:
        embedder = JinaEmbedder(
            api_key=settings.jina_api_key or "",
            model=resolved.jina_embedding_model,
            client=httpx_client,
        )
    return ChunkThenEmbedPipeline(chunker=chunker, embedder=embedder)

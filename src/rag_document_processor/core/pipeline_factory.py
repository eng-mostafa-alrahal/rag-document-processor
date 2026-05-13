from __future__ import annotations

import httpx

from rag_document_processor.application.ports.embedding_pipeline import IEmbeddingPipeline, IMacroSplitter
from rag_document_processor.core.config import Settings
from rag_document_processor.core.ingest_embedding_options import MacroKind, ResolvedIngestEmbeddingOptions
from rag_document_processor.infrastructure.embedders.jina_embedder import JinaEmbedder
from rag_document_processor.infrastructure.embedders.openai_embedder import OpenAIEmbedder
from rag_document_processor.infrastructure.pipelines.embedding_pipelines import ChunkThenEmbedPipeline, LateChunkingPipeline
from rag_document_processor.infrastructure.splitters.macro_splitters import (
    RecursiveMacroSplitter,
    SemanticMacroSplitter,
    TokenAwareMacroSplitter,
)
from rag_document_processor.infrastructure.splitters.sentence_chunker import RecursiveSentenceChunker


def build_macro_splitter(settings: Settings, macro: MacroKind) -> IMacroSplitter:
    if macro == "semantic":
        if not settings.openai_api_key:
            return RecursiveMacroSplitter()
        return SemanticMacroSplitter(openai_api_key=settings.openai_api_key)
    if macro == "token_aware":
        return TokenAwareMacroSplitter(max_tokens=settings.embedder_context_tokens)
    return RecursiveMacroSplitter()


def build_embedding_pipeline(
    settings: Settings,
    httpx_client: httpx.AsyncClient,
    resolved: ResolvedIngestEmbeddingOptions,
) -> IEmbeddingPipeline:
    macro = build_macro_splitter(settings, resolved.macro_splitter)
    if resolved.embedding_pipeline == "late_chunking":
        embedder = JinaEmbedder(
            api_key=settings.jina_api_key or "",
            model=resolved.jina_embedding_model,
            client=httpx_client,
        )
        return LateChunkingPipeline(macro_splitter=macro, embedder=embedder)
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

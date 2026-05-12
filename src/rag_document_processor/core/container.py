from __future__ import annotations

from dataclasses import dataclass

import httpx
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from rag_document_processor.application.ports.blob_storage import IBlobStorage
from rag_document_processor.application.ports.embedding_pipeline import IEmbeddingPipeline, IMacroSplitter
from rag_document_processor.application.ports.text_extractor import ITextExtractor
from rag_document_processor.core.config import Settings
from rag_document_processor.infrastructure.db.session import create_engine as create_async_db_engine
from rag_document_processor.infrastructure.db.session import create_session_factory
from rag_document_processor.infrastructure.embedders.jina_embedder import JinaEmbedder
from rag_document_processor.infrastructure.embedders.openai_embedder import OpenAIEmbedder
from rag_document_processor.infrastructure.extraction.http_url_fetcher import HttpUrlFetcher
from rag_document_processor.infrastructure.extraction.llama_cloud_parse_extractor import LlamaCloudParseExtractor
from rag_document_processor.infrastructure.extraction.llama_index_extractor import LlamaIndexTextExtractor
from rag_document_processor.infrastructure.pipelines.embedding_pipelines import ChunkThenEmbedPipeline, LateChunkingPipeline
from rag_document_processor.infrastructure.queue.celery_task_queue import CeleryTaskQueue
from rag_document_processor.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher
from rag_document_processor.infrastructure.security.jwt_service import JwtTokenService
from rag_document_processor.infrastructure.security.redis_refresh_store import RedisRefreshTokenStore
from rag_document_processor.infrastructure.sinks.redis_stream_sink import RedisStreamSink
from rag_document_processor.infrastructure.splitters.macro_splitters import (
    RecursiveMacroSplitter,
    SemanticMacroSplitter,
    TokenAwareMacroSplitter,
)
from rag_document_processor.infrastructure.splitters.sentence_chunker import RecursiveSentenceChunker
from rag_document_processor.infrastructure.storage.local_blob_storage import LocalBlobStorage
from rag_document_processor.infrastructure.storage.s3_blob_storage import S3BlobStorage


def _build_macro_splitter(settings: Settings) -> IMacroSplitter:
    if settings.macro_splitter == "semantic":
        if not settings.openai_api_key:
            return RecursiveMacroSplitter()
        return SemanticMacroSplitter(openai_api_key=settings.openai_api_key)
    if settings.macro_splitter == "token_aware":
        return TokenAwareMacroSplitter(max_tokens=settings.embedder_context_tokens)
    return RecursiveMacroSplitter()


def _build_embedding_pipeline(settings: Settings, httpx_client: httpx.AsyncClient) -> IEmbeddingPipeline:
    macro = _build_macro_splitter(settings)
    if settings.embedding_pipeline == "late_chunking":
        if not settings.jina_api_key:
            raise RuntimeError("JINA_API_KEY is required when EMBEDDING_PIPELINE=late_chunking")
        embedder = JinaEmbedder(
            api_key=settings.jina_api_key,
            model=settings.jina_embedding_model,
            client=httpx_client,
        )
        return LateChunkingPipeline(macro_splitter=macro, embedder=embedder)
    if not settings.openai_api_key and not settings.jina_api_key:
        raise RuntimeError("OPENAI_API_KEY or JINA_API_KEY required when EMBEDDING_PIPELINE=chunk_then_embed")
    chunker = RecursiveSentenceChunker()
    if settings.openai_api_key:
        embedder = OpenAIEmbedder(api_key=settings.openai_api_key, model=settings.openai_embedding_model)
    else:
        embedder = JinaEmbedder(
            api_key=settings.jina_api_key or "",
            model=settings.jina_embedding_model,
            client=httpx_client,
        )
    return ChunkThenEmbedPipeline(chunker=chunker, embedder=embedder)


def _build_blob_storage(settings: Settings) -> IBlobStorage:
    if settings.storage_backend == "s3":
        return S3BlobStorage(settings)
    return LocalBlobStorage(settings.local_storage_path)


def _build_text_extractor(settings: Settings) -> ITextExtractor:
    local = LlamaIndexTextExtractor()
    if settings.llama_cloud_api_key:
        return LlamaCloudParseExtractor(settings=settings, fallback=local)
    return local


@dataclass
class Container:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: redis.Redis
    httpx_client: httpx.AsyncClient
    password_hasher: BcryptPasswordHasher
    jwt_service: JwtTokenService
    refresh_store: RedisRefreshTokenStore
    blob_storage: IBlobStorage
    embedding_sink: RedisStreamSink
    url_fetcher: HttpUrlFetcher
    text_extractor: ITextExtractor
    embedding_pipeline: IEmbeddingPipeline
    task_queue: CeleryTaskQueue

    async def aclose(self) -> None:
        await self.httpx_client.aclose()
        await self.redis.aclose()
        await self.engine.dispose()


def build_container(settings: Settings) -> Container:
    engine = create_async_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    httpx_client = httpx.AsyncClient()
    password_hasher = BcryptPasswordHasher()
    jwt_service = JwtTokenService(settings)
    refresh_store = RedisRefreshTokenStore(redis_client)
    blob_storage = _build_blob_storage(settings)
    embedding_sink = RedisStreamSink(redis_client, maxlen=settings.redis_stream_maxlen)
    url_fetcher = HttpUrlFetcher(settings, httpx_client)
    text_extractor = _build_text_extractor(settings)
    embedding_pipeline = _build_embedding_pipeline(settings, httpx_client)
    task_queue = CeleryTaskQueue()
    return Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        redis=redis_client,
        httpx_client=httpx_client,
        password_hasher=password_hasher,
        jwt_service=jwt_service,
        refresh_store=refresh_store,
        blob_storage=blob_storage,
        embedding_sink=embedding_sink,
        url_fetcher=url_fetcher,
        text_extractor=text_extractor,
        embedding_pipeline=embedding_pipeline,
        task_queue=task_queue,
    )

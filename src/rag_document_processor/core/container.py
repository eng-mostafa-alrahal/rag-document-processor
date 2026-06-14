from __future__ import annotations

from dataclasses import dataclass

import httpx
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from rag_document_processor.application.ports.blob_storage import IBlobStorage
from rag_document_processor.application.ports.embedding_pipeline import IEmbeddingPipeline
from rag_document_processor.application.ports.text_extractor import ITextExtractor
from rag_document_processor.core.config import Settings
from rag_document_processor.core.ingest_embedding_options import resolve_ingest_embedding_options
from rag_document_processor.core.pipeline_factory import build_embedding_pipeline
from rag_document_processor.infrastructure.db.session import create_engine as create_async_db_engine
from rag_document_processor.infrastructure.db.session import create_session_factory
from rag_document_processor.infrastructure.extraction.http_url_fetcher import HttpUrlFetcher
from rag_document_processor.infrastructure.extraction.llama_cloud_parse_extractor import LlamaCloudParseExtractor
from rag_document_processor.infrastructure.extraction.llama_index_extractor import LlamaIndexTextExtractor
from rag_document_processor.infrastructure.queue.celery_task_queue import CeleryTaskQueue
from rag_document_processor.infrastructure.sinks.redis_stream_result_reader import RedisStreamResultReader
from rag_document_processor.infrastructure.sinks.redis_stream_sink import RedisStreamSink
from rag_document_processor.infrastructure.storage.local_blob_storage import LocalBlobStorage
from rag_document_processor.infrastructure.storage.s3_blob_storage import S3BlobStorage


def _build_blob_storage(settings: Settings) -> IBlobStorage:
    if settings.storage_backend == "s3":
        return S3BlobStorage(settings)
    return LocalBlobStorage(settings.local_storage_path)


def _build_text_extractor(settings: Settings) -> ITextExtractor:
    local = LlamaIndexTextExtractor()
    if settings.llama_cloud_api_key:
        return LlamaCloudParseExtractor(settings=settings, fallback=local)
    return local


def _build_embedding_pipeline(settings: Settings, httpx_client: httpx.AsyncClient) -> IEmbeddingPipeline:
    resolved = resolve_ingest_embedding_options(
        settings,
        job_embedding_pipeline=None,
        job_macro_splitter=None,
        job_embedder_provider=None,
        job_openai_embedding_model=None,
        job_jina_embedding_model=None,
    )
    return build_embedding_pipeline(settings, httpx_client, resolved)


@dataclass
class Container:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: redis.Redis
    httpx_client: httpx.AsyncClient
    blob_storage: IBlobStorage
    embedding_sink: RedisStreamSink
    ingestion_result_reader: RedisStreamResultReader
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
    blob_storage = _build_blob_storage(settings)
    embedding_sink = RedisStreamSink(redis_client, maxlen=settings.redis_stream_maxlen)
    ingestion_result_reader = RedisStreamResultReader(redis_client)
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
        blob_storage=blob_storage,
        embedding_sink=embedding_sink,
        ingestion_result_reader=ingestion_result_reader,
        url_fetcher=url_fetcher,
        text_extractor=text_extractor,
        embedding_pipeline=embedding_pipeline,
        task_queue=task_queue,
    )

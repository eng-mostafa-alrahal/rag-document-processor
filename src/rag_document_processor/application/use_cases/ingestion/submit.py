from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_document_processor.application.dtos import JobCreatedDTO
from rag_document_processor.application.ports.blob_storage import IBlobStorage
from rag_document_processor.application.ports.repositories import IJobRepository
from rag_document_processor.application.ports.task_queue import ITaskQueue
from rag_document_processor.core.config import LLAMA_PARSE_TIER_CHOICES, Settings
from rag_document_processor.core.embedding_dimensions import validate_embedding_dimensions
from rag_document_processor.core.ingest_embedding_options import (
    coerce_embedder_provider,
    coerce_embedding_model,
    coerce_embedding_pipeline,
    coerce_macro_splitter,
    resolve_ingest_embedding_options,
)
from rag_document_processor.domain.entities.job import JobStatus, SourceKind
from rag_document_processor.domain.exceptions import (
    FileTooLargeError,
    InvalidLlamaParseTierError,
    UnsupportedMimeTypeError,
)
from rag_document_processor.infrastructure.db.repositories.job_repo import SqlJobRepository


def _coerce_llama_parse_tier(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    t = str(raw).strip()
    if t not in LLAMA_PARSE_TIER_CHOICES:
        allowed = ", ".join(sorted(LLAMA_PARSE_TIER_CHOICES))
        raise InvalidLlamaParseTierError(f"llama_parse_tier must be one of: {allowed}. Got {t!r}.")
    return t


def _coerce_embedding_dim_int(raw: int | str | None) -> int | None:
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        return None
    return int(str(raw).strip())


def _prepare_ingest_embedding_fields(
    settings: Settings,
    *,
    embedding_pipeline: str | None,
    macro_splitter: str | None,
    embedder_provider: str | None,
    embedding_model: str | None,
    embedding_dimensions: int | str | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None, int | None]:
    ep = coerce_embedding_pipeline(embedding_pipeline)
    ms = coerce_macro_splitter(macro_splitter)
    prov = coerce_embedder_provider(embedder_provider)
    base = resolve_ingest_embedding_options(
        settings,
        job_embedding_pipeline=ep,
        job_macro_splitter=ms,
        job_embedder_provider=prov,
        job_openai_embedding_model=None,
        job_jina_embedding_model=None,
    )
    om: str | None = None
    jm: str | None = None
    em = coerce_embedding_model(embedding_model, field="embedding_model")
    if em is not None:
        if base.embedder == "openai":
            om = em
        else:
            jm = em
    resolved = resolve_ingest_embedding_options(
        settings,
        job_embedding_pipeline=ep,
        job_macro_splitter=ms,
        job_embedder_provider=prov,
        job_openai_embedding_model=om,
        job_jina_embedding_model=jm,
    )
    dim = _coerce_embedding_dim_int(embedding_dimensions)
    validate_embedding_dimensions(
        embedder=resolved.embedder,
        openai_embedding_model=resolved.openai_embedding_model,
        jina_embedding_model=resolved.jina_embedding_model,
        dim=dim,
    )
    return ep, ms, prov, om, jm, dim


class SubmitFileIngestionUseCase:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        blob_storage: IBlobStorage,
        task_queue: ITaskQueue,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._blobs = blob_storage
        self._queue = task_queue
        self._settings = settings

    async def execute(
        self,
        *,
        user_id: UUID,
        filename: str | None,
        content_type: str | None,
        data: bytes,
        llama_parse_tier: str | None = None,
        embedding_dimensions: int | str | None = None,
        embedding_pipeline: str | None = None,
        macro_splitter: str | None = None,
        embedder_provider: str | None = None,
        embedding_model: str | None = None,
    ) -> JobCreatedDTO:
        if len(data) > self._settings.max_upload_bytes:
            raise FileTooLargeError("Upload exceeds configured maximum size")
        ctype = (content_type or "application/octet-stream").split(";")[0].strip().lower()
        if ctype not in self._settings.allowed_mime_set:
            raise UnsupportedMimeTypeError(f"Content type not allowed: {ctype}")
        tier = _coerce_llama_parse_tier(llama_parse_tier)
        ep, ms, prov, om, jm, dims = _prepare_ingest_embedding_fields(
            self._settings,
            embedding_pipeline=embedding_pipeline,
            macro_splitter=macro_splitter,
            embedder_provider=embedder_provider,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
        )
        job_id = uuid4()
        key = f"{user_id}/{job_id}/{filename or 'upload'}"
        await self._blobs.put(key, data, content_type=ctype)
        async with self._session_factory() as session:
            jobs: IJobRepository = SqlJobRepository(session)
            await jobs.create(
                job_id=job_id,
                user_id=user_id,
                source_kind=SourceKind.FILE,
                status=JobStatus.PENDING,
                blob_key=key,
                content_type=ctype,
                original_filename=filename,
                llama_parse_tier=tier,
                embedding_dimensions=dims,
                embedding_pipeline=ep,
                macro_splitter=ms,
                embedder_provider=prov,
                openai_embedding_model=om,
                jina_embedding_model=jm,
            )
            await session.commit()
        await self._queue.enqueue_process_job(job_id)
        return JobCreatedDTO(job_id=job_id)


class SubmitUrlIngestionUseCase:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        task_queue: ITaskQueue,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._queue = task_queue
        self._settings = settings

    async def execute(
        self,
        *,
        user_id: UUID,
        url: str,
        llama_parse_tier: str | None = None,
        embedding_dimensions: int | None = None,
        embedding_pipeline: str | None = None,
        macro_splitter: str | None = None,
        embedder_provider: str | None = None,
        embedding_model: str | None = None,
    ) -> JobCreatedDTO:
        job_id = uuid4()
        tier = _coerce_llama_parse_tier(llama_parse_tier)
        ep, ms, prov, om, jm, dims = _prepare_ingest_embedding_fields(
            self._settings,
            embedding_pipeline=embedding_pipeline,
            macro_splitter=macro_splitter,
            embedder_provider=embedder_provider,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
        )
        async with self._session_factory() as session:
            jobs: IJobRepository = SqlJobRepository(session)
            await jobs.create(
                job_id=job_id,
                user_id=user_id,
                source_kind=SourceKind.URL,
                status=JobStatus.PENDING,
                source_url=url.strip(),
                llama_parse_tier=tier,
                embedding_dimensions=dims,
                embedding_pipeline=ep,
                macro_splitter=ms,
                embedder_provider=prov,
                openai_embedding_model=om,
                jina_embedding_model=jm,
            )
            await session.commit()
        await self._queue.enqueue_process_job(job_id)
        return JobCreatedDTO(job_id=job_id)


class SubmitTextIngestionUseCase:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        task_queue: ITaskQueue,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._queue = task_queue
        self._settings = settings

    async def execute(
        self,
        *,
        user_id: UUID,
        texts: list[str],
        llama_parse_tier: str | None = None,
        embedding_dimensions: int | None = None,
        embedding_pipeline: str | None = None,
        macro_splitter: str | None = None,
        embedder_provider: str | None = None,
        embedding_model: str | None = None,
    ) -> JobCreatedDTO:
        joined = "\n\n".join(t for t in texts if t)
        if not joined:
            joined = ""
        job_id = uuid4()
        tier = _coerce_llama_parse_tier(llama_parse_tier)
        ep, ms, prov, om, jm, dims = _prepare_ingest_embedding_fields(
            self._settings,
            embedding_pipeline=embedding_pipeline,
            macro_splitter=macro_splitter,
            embedder_provider=embedder_provider,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
        )
        async with self._session_factory() as session:
            jobs: IJobRepository = SqlJobRepository(session)
            await jobs.create(
                job_id=job_id,
                user_id=user_id,
                source_kind=SourceKind.TEXT,
                status=JobStatus.PENDING,
                source_text=joined,
                content_type="text/plain",
                llama_parse_tier=tier,
                embedding_dimensions=dims,
                embedding_pipeline=ep,
                macro_splitter=ms,
                embedder_provider=prov,
                openai_embedding_model=om,
                jina_embedding_model=jm,
            )
            await session.commit()
        await self._queue.enqueue_process_job(job_id)
        return JobCreatedDTO(job_id=job_id)

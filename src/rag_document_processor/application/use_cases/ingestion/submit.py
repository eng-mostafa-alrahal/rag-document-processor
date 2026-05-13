from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_document_processor.application.dtos import JobCreatedDTO
from rag_document_processor.application.ports.blob_storage import IBlobStorage
from rag_document_processor.application.ports.repositories import IJobRepository
from rag_document_processor.application.ports.task_queue import ITaskQueue
from rag_document_processor.core.config import LLAMA_PARSE_TIER_CHOICES, Settings
from rag_document_processor.domain.entities.job import JobStatus, SourceKind
from rag_document_processor.domain.exceptions import FileTooLargeError, InvalidLlamaParseTierError, UnsupportedMimeTypeError
from rag_document_processor.infrastructure.db.repositories.job_repo import SqlJobRepository


def _coerce_llama_parse_tier(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    t = str(raw).strip()
    if t not in LLAMA_PARSE_TIER_CHOICES:
        allowed = ", ".join(sorted(LLAMA_PARSE_TIER_CHOICES))
        raise InvalidLlamaParseTierError(f"llama_parse_tier must be one of: {allowed}. Got {t!r}.")
    return t


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
    ) -> JobCreatedDTO:
        if len(data) > self._settings.max_upload_bytes:
            raise FileTooLargeError("Upload exceeds configured maximum size")
        ctype = (content_type or "application/octet-stream").split(";")[0].strip().lower()
        if ctype not in self._settings.allowed_mime_set:
            raise UnsupportedMimeTypeError(f"Content type not allowed: {ctype}")
        tier = _coerce_llama_parse_tier(llama_parse_tier)
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
            )
            await session.commit()
        await self._queue.enqueue_process_job(job_id)
        return JobCreatedDTO(job_id=job_id)


class SubmitUrlIngestionUseCase:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        task_queue: ITaskQueue,
    ) -> None:
        self._session_factory = session_factory
        self._queue = task_queue

    async def execute(
        self, *, user_id: UUID, url: str, llama_parse_tier: str | None = None
    ) -> JobCreatedDTO:
        job_id = uuid4()
        tier = _coerce_llama_parse_tier(llama_parse_tier)
        async with self._session_factory() as session:
            jobs: IJobRepository = SqlJobRepository(session)
            await jobs.create(
                job_id=job_id,
                user_id=user_id,
                source_kind=SourceKind.URL,
                status=JobStatus.PENDING,
                source_url=url.strip(),
                llama_parse_tier=tier,
            )
            await session.commit()
        await self._queue.enqueue_process_job(job_id)
        return JobCreatedDTO(job_id=job_id)


class SubmitTextIngestionUseCase:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        task_queue: ITaskQueue,
    ) -> None:
        self._session_factory = session_factory
        self._queue = task_queue

    async def execute(
        self, *, user_id: UUID, texts: list[str], llama_parse_tier: str | None = None
    ) -> JobCreatedDTO:
        joined = "\n\n".join(t for t in texts if t)
        if not joined:
            joined = ""
        job_id = uuid4()
        tier = _coerce_llama_parse_tier(llama_parse_tier)
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
            )
            await session.commit()
        await self._queue.enqueue_process_job(job_id)
        return JobCreatedDTO(job_id=job_id)

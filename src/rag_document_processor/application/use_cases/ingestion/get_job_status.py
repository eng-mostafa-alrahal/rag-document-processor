from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_document_processor.application.dtos import JobStatusDTO
from rag_document_processor.application.ports.repositories import IJobRepository
from rag_document_processor.core.config import Settings
from rag_document_processor.core.embedding_dimensions import coalesce_embedding_dimensions
from rag_document_processor.core.ingest_embedding_options import resolve_ingest_embedding_options
from rag_document_processor.domain.exceptions import ForbiddenJobAccessError, JobNotFoundError
from rag_document_processor.infrastructure.db.repositories.job_repo import SqlJobRepository


class GetJobStatusUseCase:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def execute(self, *, user_id: UUID, job_id: UUID) -> JobStatusDTO:
        async with self._session_factory() as session:
            jobs: IJobRepository = SqlJobRepository(session)
            job = await jobs.get_by_id(job_id)
            if job is None:
                raise JobNotFoundError()
            if job.user_id != user_id:
                raise ForbiddenJobAccessError()
        resolved = resolve_ingest_embedding_options(
            self._settings,
            job_embedding_pipeline=job.embedding_pipeline,
            job_macro_splitter=job.macro_splitter,
            job_embedder_provider=job.embedder_provider,
            job_openai_embedding_model=job.openai_embedding_model,
            job_jina_embedding_model=job.jina_embedding_model,
        )
        effective_tier = job.llama_parse_tier or self._settings.llama_parse_tier
        effective_dims = coalesce_embedding_dimensions(job.embedding_dimensions, self._settings.embedding_dimensions)
        embedding_model = (
            resolved.openai_embedding_model if resolved.embedder == "openai" else resolved.jina_embedding_model
        )
        return JobStatusDTO(
            job_id=job.id,
            status=job.status.value,
            source_kind=job.source_kind.value,
            chunks_emitted=job.chunks_emitted,
            error_message=job.error_message,
            llama_parse_tier=effective_tier,
            embedding_dimensions=effective_dims,
            embedding_pipeline=resolved.embedding_pipeline,
            macro_splitter=resolved.macro_splitter,
            embedder_provider=resolved.embedder,
            embedding_model=embedding_model,
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat(),
        )

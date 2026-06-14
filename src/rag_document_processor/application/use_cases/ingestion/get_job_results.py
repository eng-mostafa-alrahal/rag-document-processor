from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_document_processor.application.ports.ingestion_result_reader import IIngestionResultReader
from rag_document_processor.application.ports.repositories import IJobRepository
from rag_document_processor.core.config import Settings
from rag_document_processor.core.embedding_dimensions import coalesce_embedding_dimensions
from rag_document_processor.core.ingest_embedding_options import resolve_ingest_embedding_options
from rag_document_processor.domain.entities.job import JobStatus
from rag_document_processor.domain.exceptions import JobNotFoundError, JobResultsNotReadyError
from rag_document_processor.infrastructure.db.repositories.job_repo import SqlJobRepository


@dataclass(frozen=True, slots=True)
class JobChunkResultDTO:
    index: int
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class JobResultsDTO:
    job_id: UUID
    status: str
    source_kind: str
    chunks_emitted: int
    error_message: str | None
    embedding_dimensions: int | None
    embedding_model: str
    chunks: list[JobChunkResultDTO]
    finalization_metadata: dict[str, Any] | None


class GetJobResultsUseCase:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        result_reader: IIngestionResultReader,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._reader = result_reader
        self._settings = settings

    async def execute(self, *, job_id: UUID) -> JobResultsDTO:
        async with self._session_factory() as session:
            jobs: IJobRepository = SqlJobRepository(session)
            job = await jobs.get_by_id(job_id)
            if job is None:
                raise JobNotFoundError()
            if job.status in (JobStatus.PENDING, JobStatus.PROCESSING):
                raise JobResultsNotReadyError()

        resolved = resolve_ingest_embedding_options(
            self._settings,
            job_embedding_pipeline=job.embedding_pipeline,
            job_macro_splitter=job.macro_splitter,
            job_embedder_provider=job.embedder_provider,
            job_openai_embedding_model=job.openai_embedding_model,
            job_jina_embedding_model=job.jina_embedding_model,
        )
        effective_dims = coalesce_embedding_dimensions(job.embedding_dimensions, self._settings.embedding_dimensions)
        embedding_model = (
            resolved.openai_embedding_model if resolved.embedder == "openai" else resolved.jina_embedding_model
        )

        snapshot = await self._reader.read(job_id)
        chunks = [
            JobChunkResultDTO(
                index=c.index,
                text=c.text,
                embedding=list(c.embedding),
                metadata=c.metadata,
            )
            for c in snapshot.chunks
        ]

        return JobResultsDTO(
            job_id=job.id,
            status=job.status.value,
            source_kind=job.source_kind.value,
            chunks_emitted=job.chunks_emitted,
            error_message=job.error_message,
            embedding_dimensions=effective_dims,
            embedding_model=embedding_model,
            chunks=chunks,
            finalization_metadata=snapshot.finalization_metadata,
        )

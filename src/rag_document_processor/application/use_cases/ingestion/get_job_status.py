from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_document_processor.application.dtos import JobStatusDTO
from rag_document_processor.application.ports.repositories import IJobRepository
from rag_document_processor.domain.exceptions import ForbiddenJobAccessError, JobNotFoundError
from rag_document_processor.infrastructure.db.repositories.job_repo import SqlJobRepository


class GetJobStatusUseCase:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def execute(self, *, user_id: UUID, job_id: UUID) -> JobStatusDTO:
        async with self._session_factory() as session:
            jobs: IJobRepository = SqlJobRepository(session)
            job = await jobs.get_by_id(job_id)
            if job is None:
                raise JobNotFoundError()
            if job.user_id != user_id:
                raise ForbiddenJobAccessError()
        return JobStatusDTO(
            job_id=job.id,
            status=job.status.value,
            source_kind=job.source_kind.value,
            chunks_emitted=job.chunks_emitted,
            error_message=job.error_message,
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat(),
        )

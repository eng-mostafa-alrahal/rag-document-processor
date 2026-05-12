from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rag_document_processor.domain.entities.job import IngestionJob, JobStatus, SourceKind
from rag_document_processor.infrastructure.db.models import IngestionJobModel


def _job_from_row(row: IngestionJobModel) -> IngestionJob:
    return IngestionJob(
        id=row.id,
        user_id=row.user_id,
        status=JobStatus(row.status),
        source_kind=SourceKind(row.source_kind),
        blob_key=row.blob_key,
        source_url=row.source_url,
        source_text=row.source_text,
        content_type=row.content_type,
        original_filename=row.original_filename,
        error_message=row.error_message,
        chunks_emitted=row.chunks_emitted,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        job_id: UUID,
        user_id: UUID,
        source_kind: SourceKind,
        status: JobStatus,
        blob_key: str | None = None,
        source_url: str | None = None,
        source_text: str | None = None,
        content_type: str | None = None,
        original_filename: str | None = None,
    ) -> IngestionJob:
        row = IngestionJobModel(
            id=job_id,
            user_id=user_id,
            status=status.value,
            source_kind=source_kind.value,
            blob_key=blob_key,
            source_url=source_url,
            source_text=source_text,
            content_type=content_type,
            original_filename=original_filename,
            chunks_emitted=0,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _job_from_row(row)

    async def get_by_id(self, job_id: UUID) -> IngestionJob | None:
        res = await self._session.execute(select(IngestionJobModel).where(IngestionJobModel.id == job_id))
        row = res.scalar_one_or_none()
        return _job_from_row(row) if row else None

    async def update_status(
        self,
        job_id: UUID,
        *,
        status: JobStatus,
        error_message: str | None = None,
    ) -> None:
        values: dict = {"status": status.value}
        if error_message is not None:
            values["error_message"] = error_message
        await self._session.execute(update(IngestionJobModel).where(IngestionJobModel.id == job_id).values(**values))

    async def increment_chunks(self, job_id: UUID, delta: int) -> None:
        row = await self._session.get(IngestionJobModel, job_id)
        if row is None:
            return
        row.chunks_emitted = (row.chunks_emitted or 0) + delta

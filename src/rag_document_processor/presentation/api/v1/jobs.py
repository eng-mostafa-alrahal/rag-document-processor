from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from rag_document_processor.presentation.deps import CurrentUser, get_job_status_use_case
from rag_document_processor.presentation.schemas.ingestion import JobStatusResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
async def job_status(
    job_id: UUID,
    user: CurrentUser,
    uc=Depends(get_job_status_use_case),
) -> JobStatusResponse:
    dto = await uc.execute(user_id=user.id, job_id=job_id)
    return JobStatusResponse(
        job_id=dto.job_id,
        status=dto.status,
        source_kind=dto.source_kind,
        chunks_emitted=dto.chunks_emitted,
        error_message=dto.error_message,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )

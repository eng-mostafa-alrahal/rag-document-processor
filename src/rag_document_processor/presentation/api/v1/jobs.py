from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path

from rag_document_processor.presentation.deps import CurrentUser, get_job_status_use_case
from rag_document_processor.presentation.schemas.ingestion import JobStatusResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
async def job_status(
    user: CurrentUser,
    job_id: UUID = Path(
        ...,
        description="Identifier returned in `job_id` from POST /ingest/file, /ingest/url, or /ingest/text.",
    ),
    uc=Depends(get_job_status_use_case),
) -> JobStatusResponse:
    """Poll ingestion progress and chunk counts for a job owned by the caller.

    Embedding-related fields are **effective** values (stored per-job overrides merged with
    current deployment defaults), not raw nulls for “used env default”.
    """
    dto = await uc.execute(user_id=user.id, job_id=job_id)
    return JobStatusResponse(
        job_id=dto.job_id,
        status=dto.status,
        source_kind=dto.source_kind,
        chunks_emitted=dto.chunks_emitted,
        error_message=dto.error_message,
        llama_parse_tier=dto.llama_parse_tier,
        embedding_dimensions=dto.embedding_dimensions,
        embedding_pipeline=dto.embedding_pipeline,
        macro_splitter=dto.macro_splitter,
        embedder_provider=dto.embedder_provider,
        embedding_model=dto.embedding_model,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )

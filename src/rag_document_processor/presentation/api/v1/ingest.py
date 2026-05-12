from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from rag_document_processor.presentation.deps import (
    CurrentUser,
    submit_file_use_case,
    submit_text_use_case,
    submit_url_use_case,
)
from rag_document_processor.presentation.schemas.ingestion import (
    JobCreatedResponse,
    JobStatusResponse,
    TextIngestRequest,
    UrlIngestRequest,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/file", response_model=JobCreatedResponse)
async def ingest_file(
    user: CurrentUser,
    file: UploadFile = File(...),
    uc=Depends(submit_file_use_case),
) -> JobCreatedResponse:
    data = await file.read()
    dto = await uc.execute(
        user_id=user.id,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
    )
    return JobCreatedResponse(job_id=dto.job_id)


@router.post("/url", response_model=JobCreatedResponse)
async def ingest_url(
    user: CurrentUser,
    body: UrlIngestRequest,
    uc=Depends(submit_url_use_case),
) -> JobCreatedResponse:
    dto = await uc.execute(user_id=user.id, url=str(body.url))
    return JobCreatedResponse(job_id=dto.job_id)


@router.post("/text", response_model=JobCreatedResponse)
async def ingest_text(
    user: CurrentUser,
    body: TextIngestRequest,
    uc=Depends(submit_text_use_case),
) -> JobCreatedResponse:
    dto = await uc.execute(user_id=user.id, texts=body.texts)
    return JobCreatedResponse(job_id=dto.job_id)

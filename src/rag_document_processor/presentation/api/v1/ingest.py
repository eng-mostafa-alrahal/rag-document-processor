from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from rag_document_processor.presentation.deps import (
    CurrentUser,
    submit_file_use_case,
    submit_text_use_case,
    submit_url_use_case,
)
from rag_document_processor.presentation.schemas.ingestion import (
    FORM_DESC_EMBEDDING_DIMENSIONS,
    FORM_DESC_EMBEDDING_MODEL,
    FORM_DESC_EMBEDDING_PIPELINE,
    FORM_DESC_EMBEDDER_PROVIDER,
    FORM_DESC_LLAMA_PARSE_TIER,
    FORM_DESC_MACRO_SPLITTER,
    JobCreatedResponse,
    TextIngestRequest,
    UrlIngestRequest,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/file", response_model=JobCreatedResponse)
async def ingest_file(
    user: CurrentUser,
    file: UploadFile = File(..., description="PDF, DOCX, plain text, or markdown (see ALLOWED_UPLOAD_CONTENT_TYPES on server)."),
    llama_parse_tier: str | None = Form(default=None, description=FORM_DESC_LLAMA_PARSE_TIER),
    embedding_dimensions: int | None = Form(default=None, description=FORM_DESC_EMBEDDING_DIMENSIONS),
    embedding_pipeline: str | None = Form(default=None, description=FORM_DESC_EMBEDDING_PIPELINE),
    macro_splitter: str | None = Form(default=None, description=FORM_DESC_MACRO_SPLITTER),
    embedder_provider: str | None = Form(default=None, description=FORM_DESC_EMBEDDER_PROVIDER),
    embedding_model: str | None = Form(default=None, description=FORM_DESC_EMBEDDING_MODEL),
    uc=Depends(submit_file_use_case),
) -> JobCreatedResponse:
    """Enqueue a document from a multipart upload.

    Optional form fields match the JSON body on `/ingest/url` and `/ingest/text`; omit any field to use server defaults from the environment.
    """
    data = await file.read()
    dto = await uc.execute(
        user_id=user.id,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
        llama_parse_tier=llama_parse_tier,
        embedding_dimensions=embedding_dimensions,
        embedding_pipeline=embedding_pipeline,
        macro_splitter=macro_splitter,
        embedder_provider=embedder_provider,
        embedding_model=embedding_model,
    )
    return JobCreatedResponse(job_id=dto.job_id)


@router.post("/url", response_model=JobCreatedResponse)
async def ingest_url(
    user: CurrentUser,
    body: UrlIngestRequest,
    uc=Depends(submit_url_use_case),
) -> JobCreatedResponse:
    """Enqueue ingestion by fetching a URL (for example a hosted PDF or DOCX)."""
    dto = await uc.execute(
        user_id=user.id,
        url=str(body.url),
        llama_parse_tier=body.llama_parse_tier,
        embedding_dimensions=body.embedding_dimensions,
        embedding_pipeline=body.embedding_pipeline,
        macro_splitter=body.macro_splitter,
        embedder_provider=body.embedder_provider,
        embedding_model=body.embedding_model,
    )
    return JobCreatedResponse(job_id=dto.job_id)


@router.post("/text", response_model=JobCreatedResponse)
async def ingest_text(
    user: CurrentUser,
    body: TextIngestRequest,
    uc=Depends(submit_text_use_case),
) -> JobCreatedResponse:
    """Enqueue ingestion from raw UTF-8 text segments in the JSON body."""
    dto = await uc.execute(
        user_id=user.id,
        texts=body.texts,
        llama_parse_tier=body.llama_parse_tier,
        embedding_dimensions=body.embedding_dimensions,
        embedding_pipeline=body.embedding_pipeline,
        macro_splitter=body.macro_splitter,
        embedder_provider=body.embedder_provider,
        embedding_model=body.embedding_model,
    )
    return JobCreatedResponse(job_id=dto.job_id)

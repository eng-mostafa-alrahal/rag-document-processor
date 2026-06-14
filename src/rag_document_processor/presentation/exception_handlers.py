from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse

from rag_document_processor.domain.exceptions import (
    ApiKeyNotFoundError,
    DomainError,
    FileTooLargeError,
    InvalidEmbeddingDimensionsError,
    InvalidIngestEmbeddingOptionsError,
    InvalidLlamaParseTierError,
    JobNotFoundError,
    JobResultsNotReadyError,
    UnsupportedMimeTypeError,
    UrlFetchError,
)


def _err(detail: str, code: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail, "code": code})


def register_exception_handlers(app) -> None:
    @app.exception_handler(ApiKeyNotFoundError)
    async def _api_key_nf(_: Request, __: ApiKeyNotFoundError) -> JSONResponse:
        return _err("API key not found", "api_key_not_found", status.HTTP_404_NOT_FOUND)

    @app.exception_handler(FileTooLargeError)
    async def _too_large(_: Request, exc: FileTooLargeError) -> JSONResponse:
        return _err(str(exc) or "Payload too large", "payload_too_large", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

    @app.exception_handler(UnsupportedMimeTypeError)
    async def _mime(_: Request, exc: UnsupportedMimeTypeError) -> JSONResponse:
        return _err(str(exc), "unsupported_media_type", status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    @app.exception_handler(InvalidLlamaParseTierError)
    async def _bad_parse_tier(_: Request, exc: InvalidLlamaParseTierError) -> JSONResponse:
        return _err(str(exc), "invalid_llama_parse_tier", status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(InvalidEmbeddingDimensionsError)
    async def _bad_embedding_dim(_: Request, exc: InvalidEmbeddingDimensionsError) -> JSONResponse:
        body: dict[str, object] = {"detail": str(exc), "code": "invalid_embedding_dimensions"}
        body.update(exc.payload)
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body)

    @app.exception_handler(InvalidIngestEmbeddingOptionsError)
    async def _bad_ingest_embed_opts(_: Request, exc: InvalidIngestEmbeddingOptionsError) -> JSONResponse:
        return _err(str(exc), "invalid_ingest_embedding_options", status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(UrlFetchError)
    async def _url(_: Request, exc: UrlFetchError) -> JSONResponse:
        return _err(str(exc), "url_fetch_error", status.HTTP_400_BAD_REQUEST)

    @app.exception_handler(JobNotFoundError)
    async def _job_nf(_: Request, __: JobNotFoundError) -> JSONResponse:
        return _err("Job not found", "job_not_found", status.HTTP_404_NOT_FOUND)

    @app.exception_handler(JobResultsNotReadyError)
    async def _job_results_not_ready(_: Request, __: JobResultsNotReadyError) -> JSONResponse:
        return _err(
            "Ingestion results not ready; poll GET /jobs/{job_id} until status is completed or failed",
            "job_results_not_ready",
            status.HTTP_409_CONFLICT,
        )

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return _err(str(exc) or "Bad request", "domain_error", status.HTTP_400_BAD_REQUEST)

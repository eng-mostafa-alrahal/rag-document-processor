from __future__ import annotations

from fastapi import APIRouter

from rag_document_processor.presentation.api.v1 import auth, embedding_catalog, ingest, jobs
from rag_document_processor.presentation.schemas.common import HealthResponse

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(embedding_catalog.router)
api_router.include_router(ingest.router)
api_router.include_router(jobs.router)


@api_router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()

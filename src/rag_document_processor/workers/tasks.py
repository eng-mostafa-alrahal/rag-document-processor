from __future__ import annotations

import asyncio
import logging

from rag_document_processor.application.use_cases.ingestion.process_job import ProcessIngestionJobUseCase
from rag_document_processor.core.container import build_container
from rag_document_processor.core.config import get_settings

from .celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="rag_document_processor.workers.tasks.process_ingestion_job")
def process_ingestion_job(job_id: str) -> None:
    asyncio.run(_async_process(job_id))


async def _async_process(job_id: str) -> None:
    settings = get_settings()
    container = build_container(settings)
    try:
        use_case = ProcessIngestionJobUseCase(
            session_factory=container.session_factory,
            blob_storage=container.blob_storage,
            url_fetcher=container.url_fetcher,
            text_extractor=container.text_extractor,
            httpx_client=container.httpx_client,
            sink=container.embedding_sink,
            settings=settings,
        )
        await use_case.execute(job_id)
    finally:
        await container.aclose()

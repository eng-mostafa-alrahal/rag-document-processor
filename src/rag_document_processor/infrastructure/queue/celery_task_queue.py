from __future__ import annotations

import asyncio
from uuid import UUID

from rag_document_processor.workers.celery_app import celery_app


class CeleryTaskQueue:
    async def enqueue_process_job(self, job_id: UUID) -> None:
        await asyncio.to_thread(
            celery_app.send_task,
            "rag_document_processor.workers.tasks.process_ingestion_job",
            args=[str(job_id)],
            queue=celery_app.conf.task_default_queue,
        )

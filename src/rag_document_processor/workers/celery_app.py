from __future__ import annotations

import os

from celery import Celery


def make_celery() -> Celery:
    broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
    backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    queue = os.environ.get("CELERY_TASK_DEFAULT_QUEUE", "ingest")
    app = Celery("rag_document_processor", broker=broker, backend=backend)
    app.conf.task_default_queue = queue
    app.conf.imports = ("rag_document_processor.workers.tasks",)
    return app


celery_app = make_celery()

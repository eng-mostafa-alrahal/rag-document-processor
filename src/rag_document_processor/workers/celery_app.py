from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    _PROJECT_ROOT = Path(__file__).resolve().parents[3]
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    pass

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

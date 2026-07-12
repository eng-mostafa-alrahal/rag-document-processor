"""Run ProcessIngestionJobUseCase for an existing job id (no Celery).

Submit a job via Bruno/curl first, then debug the worker path with breakpoints in:
  - application/use_cases/ingestion/process_job.py
  - infrastructure/pipelines/embedding_pipelines.py

Usage:

    uv run python scripts/debug_process_job.py <job-uuid>

Or: Run and Debug → "Debug: process job by id" (prompts for UUID).

Requires Postgres + Redis from docker compose and a valid JINA_API_KEY for late_chunking.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import UUID

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rag_document_processor.application.use_cases.ingestion.process_job import (  # noqa: E402
    ProcessIngestionJobUseCase,
)
from rag_document_processor.core.config import get_settings  # noqa: E402
from rag_document_processor.core.container import build_container  # noqa: E402


async def _main(job_id: str) -> int:
    UUID(job_id)  # validate
    settings = get_settings()
    container = build_container(settings)
    try:
        uc = ProcessIngestionJobUseCase(
            session_factory=container.session_factory,
            blob_storage=container.blob_storage,
            url_fetcher=container.url_fetcher,
            text_extractor=container.text_extractor,
            httpx_client=container.httpx_client,
            sink=container.embedding_sink,
            settings=settings,
        )
        print(f"Processing job {job_id} ...")
        await uc.execute(job_id)
        print("Done. Fetch results: GET /api/v1/jobs/{id}/results")
    finally:
        await container.aclose()
    return 0


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Usage: uv run python scripts/debug_process_job.py <job-uuid>", file=sys.stderr)
        return 1
    return asyncio.run(_main(sys.argv[1].strip()))


if __name__ == "__main__":
    raise SystemExit(main())

# RAG Ingestion Service

FastAPI + Clean Architecture ingestion pipeline: upload file, URL, or text; Celery workers extract text, run pluggable embedding pipelines, and stage vectors on **Redis Streams** for downstream consumers.

## Quick start

1. Copy `.env.example` to `.env` and set secrets.
2. `docker compose up -d` (Postgres, Redis, MinIO).
3. `uv sync --extra dev`
4. `uv run alembic upgrade head`
5. `uv run uvicorn rag_document_processor.main:app --reload --app-dir src`
6. In another terminal: `uv run celery -A rag_document_processor.workers.celery_app worker -l info`

## API

- `POST /api/v1/auth/register` — register
- `POST /api/v1/auth/login` — access + refresh tokens
- `POST /api/v1/auth/refresh` — rotate refresh token
- `POST /api/v1/auth/logout` — revoke refresh jti (Redis)
- `POST /api/v1/ingest/file` — multipart upload (Bearer)
- `POST /api/v1/ingest/url` — JSON `{ "url": "..." }`
- `POST /api/v1/ingest/text` — JSON `{ "texts": ["..."] }`
- `GET /api/v1/jobs/{job_id}` — job status

## Configuration

See `.env.example`. Key settings:

- `STORAGE_BACKEND=local|s3`
- `EMBEDDING_PIPELINE=late_chunking|chunk_then_embed`
- `MACRO_SPLITTER=semantic|recursive|token_aware`
- Jina / OpenAI keys when using those embedders

## Tests

```bash
uv run pytest tests/unit -q
uv run pytest tests/integration -m integration -q   # requires Docker
```

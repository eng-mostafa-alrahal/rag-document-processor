# RAG Document Processor

FastAPI + Clean Architecture ingestion pipeline: upload file, URL, or text; Celery workers extract text, run pluggable embedding pipelines, and stage vectors on **Redis Streams** for downstream consumers.

## Quick start

1. Copy `.env.example` to `.env` and set secrets.
2. `docker compose up -d` (Postgres, Redis, MinIO).
3. `uv sync --extra dev`
4. `uv run alembic upgrade head` (optional in dev: with `ENV=dev`, the API can create the DB if missing when `DATABASE_AUTO_CREATE` is on, then run migrations when `DATABASE_AUTO_MIGRATE` is on—both default on in dev)
5. `uv run uvicorn rag_document_processor.main:app --reload --app-dir src`
6. In another terminal: `uv run celery -A rag_document_processor.workers.celery_app worker -l info`

## API

- `POST /api/v1/auth/register` — register
- `POST /api/v1/auth/login` — access + refresh tokens
- `POST /api/v1/auth/refresh` — rotate refresh token
- `POST /api/v1/auth/logout` — revoke refresh jti (Redis)
- `POST /api/v1/ingest/file` — multipart upload (Bearer); optional form field `llama_parse_tier` for LlamaCloud PDF/DOCX (`fast` | `cost_effective` | `agentic` | `agentic_plus`; defaults from `LLAMA_PARSE_TIER` in env when omitted)
- `POST /api/v1/ingest/url` — JSON `{ "url": "...", "llama_parse_tier": "fast" }` (`llama_parse_tier` optional, same values)
- `POST /api/v1/ingest/text` — JSON `{ "texts": ["..."] }` (optional `llama_parse_tier` accepted; ignored for plain text)
- `GET /api/v1/jobs/{job_id}` — job status (includes `llama_parse_tier` if set at submit time)

## Configuration

See `.env.example`. Key settings:

- `DATABASE_AUTO_MIGRATE` — when true, the API runs `alembic upgrade head` on startup (default true for `ENV=dev|development|test`, false for other environments unless you set it explicitly).
- `DATABASE_AUTO_CREATE` — when true, create the target Postgres database if missing before migrations (default true in dev/test like auto-migrate; needs a DB name matching `[A-Za-z_][A-Za-z0-9_]{0,62}` and a role with permission to create databases; turn off for managed Postgres).
- `STORAGE_BACKEND=local|s3`
- `EMBEDDING_PIPELINE=late_chunking|chunk_then_embed`
- `MACRO_SPLITTER=semantic|recursive|token_aware`
- Jina / OpenAI keys when using those embedders
- `LLAMA_CLOUD_API_KEY` / `LLAMA_PARSE_TIER` — optional cloud PDF/DOCX parse; tier defaults from env, overridable per ingest request

## Tests

```bash
uv run pytest tests/unit -q
uv run pytest tests/integration -m integration -q   # requires Docker
```

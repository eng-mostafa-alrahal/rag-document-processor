# RAG Document Processor

FastAPI + Clean Architecture ingestion pipeline: upload file, URL, or text; Celery workers extract text, run pluggable embedding pipelines, and stage vectors on **Redis Streams** for downstream consumers.

## Documentation

- **[docs/ONBOARDING.md](docs/ONBOARDING.md)** — onboarding for new developers: architecture, local setup, ingest flow, tests, migrations, pitfalls, and **Cursor** tips (`@`-mentions).
- **[docs/DEPLOY_GCP.md](docs/DEPLOY_GCP.md)** — budget GCP VM deploy + **GitHub Actions** CI/CD.
- **[AGENTS.md](AGENTS.md)** — short project map for **AI agents** (Cursor); keep this file updated when the high-level layout or commands change.

## Quick start

1. Copy `.env.example` to `.env` and set secrets.
2. `docker compose up -d` (Postgres, Redis, MinIO).
3. `uv sync --extra dev`
4. `uv run alembic upgrade head` (optional in dev: with `ENV=dev`, the API can create the DB if missing when `DATABASE_AUTO_CREATE` is on, then run migrations when `DATABASE_AUTO_MIGRATE` is on—both default on in dev)
5. `uv run uvicorn rag_document_processor.main:app --reload --app-dir src`
6. In another terminal: `uv run celery -A rag_document_processor.workers.celery_app worker -l info` (on Windows use `--pool=solo` if the worker crashes)

## API

- `POST /api/v1/auth/register` — register
- `POST /api/v1/auth/login` — access + refresh tokens
- `POST /api/v1/auth/refresh` — rotate refresh token
- `POST /api/v1/auth/logout` — revoke refresh jti (Redis)
- `POST /api/v1/ingest/file` — multipart upload (Bearer); optional `llama_parse_tier`, `embedding_pipeline`, `macro_splitter`, `embedder_provider`, `embedding_model`, `embedding_dimensions` (see OpenAPI `/docs`)
- `POST /api/v1/ingest/url` — JSON with `url` and the same optional ingest fields as file/text
- `POST /api/v1/ingest/text` — JSON `{ "texts": ["..."] }` plus optional ingest fields
- `GET /api/v1/jobs/{job_id}` — job status (effective resolved tier, pipeline, splitter, provider, `embedding_model`, dimensions, etc.)
- `GET /api/v1/embeddings/dimension-constraints` — allowed embedding output sizes by model family (for clients and OpenAPI users)

See **[docs/ONBOARDING.md](docs/ONBOARDING.md)** for architecture and operational detail.

## Configuration

See `.env.example`. Key settings:

- `DATABASE_AUTO_MIGRATE` — when true, the API runs `alembic upgrade head` on startup (default true for `ENV=dev|development|test`, false for other environments unless you set it explicitly).
- `DATABASE_AUTO_CREATE` — when true, create the target Postgres database if missing before migrations (default true in dev/test like auto-migrate; needs a DB name matching `[A-Za-z_][A-Za-z0-9_]{0,62}` and a role with permission to create databases; turn off for managed Postgres).
- `STORAGE_BACKEND=local|s3`
- `EMBEDDING_PIPELINE=late_chunking|chunk_then_embed`
- `MACRO_SPLITTER=semantic|recursive|token_aware`
- `EMBEDDING_DIMENSIONS` — optional default output size when a job omits `embedding_dimensions` (must fit the active embedder model)
- Jina / OpenAI keys when using those embedders
- `LLAMA_CLOUD_API_KEY` / `LLAMA_PARSE_TIER` — optional cloud PDF/DOCX parse; tier defaults from env, overridable per ingest request

## Tests

```bash
uv run pytest tests/unit -q
uv run pytest tests/integration -m integration -q   # requires Docker
```

## CI/CD

GitHub Actions runs unit tests and a Docker build on every push/PR to `main` or `stage` (`.github/workflows/ci.yml`). Pushes to **`stage`** deploy to a GCP VM over SSH (`.github/workflows/deploy.yml`). See **[docs/DEPLOY_GCP.md](docs/DEPLOY_GCP.md)** for VM setup and GitHub secrets.

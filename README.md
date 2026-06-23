# RAG Document Processor

FastAPI + Clean Architecture ingestion pipeline: upload file, URL, or text; Celery workers extract text, run pluggable embedding pipelines, and stage vectors on **Redis Streams** for downstream consumers.

## Documentation

- **[docs/API_INTEGRATION.md](docs/API_INTEGRATION.md)** — **for other teams / projects**: authentication, ingest flow, polling, fetching results, code examples (Python, JS, curl).
- **[docs/ONBOARDING.md](docs/ONBOARDING.md)** — onboarding for new developers: architecture, local setup, ingest flow, tests, migrations, pitfalls, and **Cursor** tips (`@`-mentions).
- **[docs/DEPLOY_CLOUD_RUN.md](docs/DEPLOY_CLOUD_RUN.md)** — **step-by-step production deploy** (Cloud Run + Cloud SQL + GitHub Actions).
- **[docs/DEPLOY_GCP.md](docs/DEPLOY_GCP.md)** — legacy VM deploy (deprecated).
- **[AGENTS.md](AGENTS.md)** — short project map for **AI agents** (Cursor); keep this file updated when the high-level layout or commands change.

## Quick start

1. Copy `.env.example` to `.env` and set secrets.
2. `docker compose up -d` (Postgres, Redis, MinIO).
3. `uv sync --extra dev`
4. `uv run alembic upgrade head` (optional in dev: with `ENV=dev`, the API can create the DB if missing when `DATABASE_AUTO_CREATE` is on, then run migrations when `DATABASE_AUTO_MIGRATE` is on—both default on in dev)
5. `uv run uvicorn rag_document_processor.main:app --reload --app-dir src`
6. In another terminal: `uv run celery -A rag_document_processor.workers.celery_app worker -l info` (on Windows use `--pool=solo` if the worker crashes)

## Authentication

The service is API-key based: any client holding a valid key may use it. Keys are
stored hashed in Postgres and managed by an operator.

- Clients send their key as the `X-API-Key` header on ingest/jobs requests.
- Key management endpoints (`/api/v1/api-keys`) are protected by a shared admin secret
  sent as the `X-Admin-Secret` header (set `API_KEY_ADMIN_SECRET`).
- Bootstrap the first key from the CLI: `uv run python scripts/create_api_key.py "my client"`.
  The full secret is shown **once**.

## API

- `POST /api/v1/api-keys` — create a key (admin; returns the secret once)
- `GET /api/v1/api-keys` — list keys (admin; secrets never returned)
- `DELETE /api/v1/api-keys/{key_id}` — revoke a key (admin)
- `POST /api/v1/ingest/file` — multipart upload (`X-API-Key`); optional `llama_parse_tier`, `embedding_pipeline`, `macro_splitter`, `embedder_provider`, `embedding_model`, `embedding_dimensions` (see OpenAPI `/docs`)
- `POST /api/v1/ingest/url` — JSON with `url` and the same optional ingest fields as file/text
- `POST /api/v1/ingest/text` — JSON `{ "texts": ["..."] }` plus optional ingest fields
- `GET /api/v1/jobs/{job_id}` — job status (effective resolved tier, pipeline, splitter, provider, `embedding_model`, dimensions, etc.)
- `GET /api/v1/jobs/{job_id}/results` — all embedded chunks (text + vectors + metadata) for downstream RAG; poll status until `completed` or `failed`
- `GET /api/v1/embeddings/dimension-constraints` — allowed embedding output sizes by model family (for clients and OpenAPI users)

See **[docs/API_INTEGRATION.md](docs/API_INTEGRATION.md)** for a full guide for external consumers, or **[docs/ONBOARDING.md](docs/ONBOARDING.md)** for architecture and operational detail.

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

GitHub Actions runs unit tests and a Docker build on every push/PR to `main` or `stage` (`.github/workflows/ci.yml`). A separate **Deploy** workflow (`.github/workflows/deploy.yml`) deploys to **Google Cloud Run on push to `stage` only** (never `main`). See **[docs/DEPLOY_CLOUD_RUN.md](docs/DEPLOY_CLOUD_RUN.md)** for GCP setup and GitHub secrets.

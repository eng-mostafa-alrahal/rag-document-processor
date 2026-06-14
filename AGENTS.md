# AGENTS.md — RAG Document Processor

Concise context for **AI coding agents** (e.g. Cursor). For full onboarding, read **`docs/ONBOARDING.md`**.

## Project

FastAPI API + Celery workers: ingest **file / URL / text** → extract → embed → emit chunks to **Redis Streams**. Postgres for jobs + API keys; optional **LlamaCloud** parse for PDF/DOCX.

**Auth:** API-key based (no users/JWT). Clients send `X-API-Key`; keys are stored hashed in `api_keys` and managed via `/api/v1/api-keys` (guarded by `API_KEY_ADMIN_SECRET` sent as `X-Admin-Secret`). Bootstrap with `scripts/create_api_key.py`. Jobs are global (no per-key ownership).

## Commands (from repo root)

```bash
uv sync --extra dev
docker compose up -d
uv run alembic upgrade head
uv run uvicorn rag_document_processor.main:app --reload --app-dir src
uv run celery -A rag_document_processor.workers.celery_app worker -l info
uv run pytest tests/unit -q
```

Windows Celery: add `--pool=solo` if the default pool fails.

## Layout

- `src/rag_document_processor/domain/` — entities & domain errors only
- `application/` — use cases, ports (interfaces), DTOs
- `infrastructure/` — DB, Redis, S3, HTTP, embedders, pipelines, extractors
- `presentation/` — FastAPI routes, schemas, exception handlers, deps
- `core/` — Settings, container, embedding dimension rules, ingest option resolution
- `workers/` — Celery app + tasks
- `alembic/versions/` — migrations

**Do not** import FastAPI/SQLAlchemy/Celery into `domain/`.

## Ingest / embedding

- Submit paths: `application/use_cases/ingestion/submit.py` (`_prepare_ingest_embedding_fields`).
- Worker: `application/use_cases/ingestion/process_job.py`.
- Public ingest body uses **`embedding_model`** (one field); DB still stores provider-specific columns internally.
- Dimension validation: `core/embedding_dimensions.py`; discovery route: `GET /api/v1/embeddings/dimension-constraints`.

## Config

`core/config.py` + `.env.example`. New env vars: document in `.env.example` and wire through `Settings`.

## Tests

Prefer unit tests under `tests/unit/`; integration tests may need Docker (`tests/integration/`).

## Deploy / CI

- **CI:** `.github/workflows/ci.yml` — unit tests + Docker build on push/PR.
- **CD:** `.github/workflows/deploy.yml` — on push to **`stage`**, deploy **API + worker** to **Google Cloud Run**.
- **Docs:** `docs/DEPLOY_CLOUD_RUN.md` (primary), `docs/DEPLOY_GCP.md` (legacy VM), `docker-compose.prod.yml` (local/legacy VM stack).

## When unsure

Read `docs/ONBOARDING.md` or ask the user which layer owns the change.

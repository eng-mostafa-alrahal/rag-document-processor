# Onboarding: RAG Document Processor

Welcome. This guide orients you to the codebase, local development, and how we extend the system. It is written for humans and for **Cursor** (use `@docs/ONBOARDING.md` or `@AGENTS.md` in chat to ground the agent).

## What this service does

- **HTTP API (FastAPI)** accepts ingestion jobs: **file** (multipart), **URL**, or **raw text**.
- **Celery workers** pull jobs from the queue, extract text, run an **embedding pipeline**, and write vector chunks to a **Redis Stream** for downstream RAG/indexing.
- **Postgres** stores API keys, jobs, and job metadata. **Blob storage** (local or S3) holds uploaded bytes.

## Prerequisites

- **Python** 3.11+ (see `pyproject.toml`).
- **[uv](https://docs.astral.sh/uv/)** for dependencies and virtualenv (repo assumes `uv run …`).
- **Docker** (optional but recommended) for Postgres + Redis + MinIO via `docker compose`.
- API keys as needed: **Jina**, **OpenAI**, **LlamaCloud** (for cloud PDF/DOCX parse)—see `.env.example`.

## First-day setup

1. **Clone** the repo and open the **repository root** in Cursor (so paths and rules resolve correctly).

2. **Environment**
   - Copy `.env.example` → `.env`.
   - For local Docker: defaults in `.env.example` often match `docker compose` (Postgres `rag`/`rag`, Redis `6379`).
   - For **cloud Redis** (e.g. Redis Cloud): use the full URL including DB index; ensure **broker**, **results**, and **stream** DB indices match how you deploy (see `.env.example` comments).

3. **Infrastructure**
   ```bash
   docker compose up -d
   ```

4. **Python deps**
   ```bash
   uv sync --extra dev
   ```

5. **Database migrations**
   ```bash
   uv run alembic upgrade head
   ```
   In **dev**, you can enable `DATABASE_AUTO_CREATE` / `DATABASE_AUTO_MIGRATE` so the API creates the DB and migrates on startup—see `README.md` and `.env.example`.

6. **Run the API** (from repo root; `src` on path)
   ```bash
   uv run uvicorn rag_document_processor.main:app --reload --app-dir src
   ```
   Open **http://127.0.0.1:8000/docs** for Swagger (`X-API-Key` auth for protected routes).

7. **Run a Celery worker** (second terminal; same `.env`)
   ```bash
   uv run celery -A rag_document_processor.workers.celery_app worker -l info
   ```
   On **Windows**, if you see pool-related crashes, try `--pool=solo`.

8. **Smoke test**
   - Mint a key: `uv run python scripts/create_api_key.py "dev"`, then submit a small **text** ingest with the `X-API-Key` header and poll **`GET /api/v1/jobs/{job_id}`**.

## Architecture (Clean Architecture)

Code lives under `src/rag_document_processor/`:

| Layer | Role | Examples |
|--------|------|-----------|
| **domain** | Entities, value objects, domain exceptions—**no** I/O or framework imports. | `domain/entities/job.py`, `domain/exceptions.py` |
| **application** | Use cases, ports (interfaces), DTOs—**orchestration** only. | `application/use_cases/ingestion/submit.py`, `application/ports/*.py` |
| **infrastructure** | Adapters: DB, Redis, HTTP, S3, embedders, pipelines, extractors. | `infrastructure/db/`, `infrastructure/embedders/`, `infrastructure/pipelines/` |
| **presentation** | FastAPI routes, Pydantic schemas, DI wiring, exception handlers. | `presentation/api/v1/`, `presentation/schemas/` |
| **core** | App-wide config, DI container, cross-cutting validation (settings, embedding rules). | `core/config.py`, `core/embedding_dimensions.py`, `core/container.py` |
| **workers** | Celery app and task entrypoints. | `workers/celery_app.py`, `workers/tasks.py` |

**Dependency rule:** outer layers depend inward; **domain** must not depend on FastAPI, SQLAlchemy, or Celery.

### Ingest flow (mental model)

1. **Submit** (`presentation` → `Submit*UseCase`) validates options, persists a **job** row, enqueues Celery.
2. **Worker** runs `ProcessIngestionJobUseCase`: load job → extract text → `resolve_ingest_embedding_options` + `build_embedding_pipeline` → stream chunks to **Redis** via `IEmbeddingSink`.

When you add behavior, ask: *Is this business rule (domain), orchestration (application), or an adapter (infrastructure)?*

## Configuration

- **Single source of truth for env vars:** `core/config.py` (Pydantic `Settings`) and **`.env.example`** (document every variable you add).
- Per-job overrides (embedding pipeline, splitter, provider, **embedding_model**, dimensions, Llama tier) are validated at **submit** and again in **process_job** against resolved settings.

## API surface (quick reference)

- **Auth / API keys:** `POST/GET …/api-keys`, `DELETE …/api-keys/{id}` (admin via `X-Admin-Secret`). Clients authenticate with `X-API-Key`.
- **Ingest:** `POST …/ingest/file`, `…/ingest/url`, `…/ingest/text` (`X-API-Key`). Optional fields are described in OpenAPI (`/docs`).
- **Jobs:** `GET …/jobs/{job_id}` returns **effective** resolved options (not raw nulls for “used env default”). `GET …/jobs/{job_id}/results` returns all embedded chunks for RAG consumers (API reads Redis internally).
- **Embedding dimensions:** `GET …/embeddings/dimension-constraints` lists supported **min/max** (and notes) per model family for OpenAPI clients.

## Tests

```bash
uv run pytest tests/unit -q
uv run pytest tests/integration -m integration -q   # needs Docker / testcontainers
```

Add **unit** tests next to the module you change; use **integration** when real Postgres/Redis behavior matters.

## Database migrations

- Alembic config: `alembic.ini`, env: `alembic/env.py`.
- New migration: `uv run alembic revision -m "describe_change"` then edit the revision under `alembic/versions/`.
- Keep `src/.../infrastructure/db/models.py` in sync with migrations.

## Common pitfalls

- **API without worker:** jobs stay `pending` / `processing` forever—always run Celery with the **same** `CELERY_*` and Redis settings as the API.
- **Redis `Connection closed by server`:** often idle timeouts on hosted Redis; consider retries or connection tuning.
- **LlamaCloud `fast` tier:** markdown expansion is not supported; the extractor uses **text-only** expand for `fast` (see `llama_cloud_parse_extractor.py`).
- **Embedding dimensions:** must match the **resolved** model; mismatches return **422** with structured fields (`embedding_model`, `allowed_dimensions_min`, etc.).

## Working in Cursor

1. **Open the repo root** so `.cursor/rules` and `AGENTS.md` apply.
2. **@ files** you are changing (e.g. `@src/rag_document_processor/application/use_cases/ingestion/submit.py`) to reduce hallucinations.
3. **@AGENTS.md** for a short project map; **@docs/ONBOARDING.md** for this full guide.
4. For large changes, ask the agent to **follow the layer rules** in `.cursor/rules/rag-document-processor.mdc`.
5. After edits, run **`uv run pytest`** (or targeted paths) yourself or ask the agent to run them.

## Where to look first (by task)

| Task | Start here |
|------|------------|
| New ingest field / validation | `presentation/schemas/ingestion.py`, `submit.py`, `process_job.py` |
| New embedding provider | `application/ports/embedding_pipeline.py`, `infrastructure/embedders/`, `core/pipeline_factory.py` |
| Dimension rules / OpenAPI catalog | `core/embedding_dimensions.py`, `presentation/api/v1/embedding_catalog.py` |
| Job status shape | `get_job_status.py`, `presentation/schemas/ingestion.py` (`JobStatusResponse`) |
| New HTTP route | `presentation/api/v1/`, `router.py`, `deps.py` |
| Celery behavior | `workers/tasks.py`, `process_job.py` |

## Deploy / production

Production runs on **Google Cloud Run** — follow the step-by-step guide in [DEPLOY_CLOUD_RUN.md](./DEPLOY_CLOUD_RUN.md). CI deploys on push to `stage`.

## Questions

Prefer **Slack / issue / PR comment** per your team norm. For code intent, **git blame** and **tests** are the other source of truth.

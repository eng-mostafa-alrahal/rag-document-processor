# Deploy on Google Cloud Run + GitHub Actions

Production deployment uses **Cloud Run** (HTTPS API + background worker), **Cloud SQL** (Postgres), **Redis** (broker + streams — e.g. Redis Cloud), and **GCS** (upload storage). **GitHub Actions** builds the Docker image and deploys on push to **`stage`**.

The old **GCP VM + SSH** flow is legacy — see [DEPLOY_GCP.md](./DEPLOY_GCP.md#legacy-vm-deploy-deprecated).

## Architecture

```
GitHub (push to stage)
    │
    ├─ CI ──► unit tests + Docker build
    │
    └─ Deploy ──► Artifact Registry
                      ├─ Cloud Run: rag-api      (public HTTPS)
                      └─ Cloud Run: rag-worker   (internal, always on)
                            │
                            ├─ Cloud SQL (Postgres)
                            ├─ Redis Cloud (Celery + streams)
                            └─ GCS bucket (uploads)
```

| Component | Where it runs |
|-----------|----------------|
| FastAPI API | Cloud Run `rag-api` |
| Celery worker | Cloud Run `rag-worker` (`min-instances: 1`, CPU always on) |
| Postgres | **Cloud SQL** |
| Redis | **External** (Redis Cloud recommended) or Memorystore |
| File uploads | **GCS** (S3-compatible HMAC keys) |

---

## Part 1 — One-time GCP setup

Install [gcloud CLI](https://cloud.google.com/sdk/docs/install) and authenticate:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

Run the helper script (creates Artifact Registry, Cloud SQL, GCS bucket, deploy service account):

```bash
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=us-central1
export SQL_ROOT_PASSWORD='strong-root-password'
export SQL_RAG_PASSWORD='strong-rag-password'
chmod +x scripts/setup-gcp-cloudrun.sh
./scripts/setup-gcp-cloudrun.sh
```

Or create resources manually in the console (see sections below).

### Cloud SQL connection name

Note the instance connection name (for GitHub secret `CLOUD_SQL_CONNECTION_NAME`):

```text
YOUR_PROJECT_ID:us-central1:rag-sql
```

### Database URLs (Cloud Run + Cloud SQL socket)

```text
postgresql+asyncpg://rag:PASSWORD@/rag?host=/cloudsql/PROJECT:REGION:INSTANCE
postgresql://rag:PASSWORD@/rag?host=/cloudsql/PROJECT:REGION:INSTANCE
```

### GCS for uploads

Create a bucket, then [HMAC keys](https://cloud.google.com/storage/docs/authentication/hmackeys) for S3-compatible access:

```env
STORAGE_BACKEND=s3
S3_BUCKET_NAME=your-project-rag-uploads
S3_ENDPOINT_URL=https://storage.googleapis.com
S3_ACCESS_KEY_ID=<HMAC access id>
S3_SECRET_ACCESS_KEY=<HMAC secret>
S3_REGION=auto
```

### Redis

Use **Redis Cloud** (or Memorystore). Point all three URLs at your instance (use `/0`, `/1`, `/2` or all `/0` on hosts that only allow DB 0):

```env
REDIS_URL=rediss://...
CELERY_BROKER_URL=rediss://...
CELERY_RESULT_BACKEND=rediss://...
```

---

## Part 2 — GitHub Actions secrets

**Settings → Environments → staging → Secrets**

### GCP / deploy

| Secret | Example | Description |
|--------|---------|-------------|
| `GCP_PROJECT_ID` | `my-project-123` | GCP project |
| `GCP_REGION` | `us-central1` | Cloud Run + Artifact Registry region |
| `GCP_SA_KEY` | `{ "type": "service_account", ... }` | JSON key for deploy SA (from setup script) |
| `CLOUD_SQL_CONNECTION_NAME` | `project:region:rag-sql` | Cloud SQL instance connection |

### Application (same values Cloud Run receives)

| Secret | Required | Description |
|--------|----------|-------------|
| `DATABASE_URL` | Yes | Async Postgres URL with `/cloudsql/` host |
| `DATABASE_URL_SYNC` | Yes | Sync URL for Alembic |
| `REDIS_URL` | Yes | Redis for streams |
| `CELERY_BROKER_URL` | Yes | Celery broker |
| `CELERY_RESULT_BACKEND` | Yes | Celery results |
| `API_KEY_ADMIN_SECRET` | Yes | Admin header for `/api-keys` |
| `OPENAI_API_KEY` | Yes* | *Or Jina if using Jina embedder |
| `JINA_API_KEY` | Optional | |
| `LLAMA_CLOUD_API_KEY` | Optional | PDF/DOCX cloud parse |
| `S3_BUCKET_NAME` | Yes | GCS bucket name |
| `S3_ACCESS_KEY_ID` | Yes | GCS HMAC access key |
| `S3_SECRET_ACCESS_KEY` | Yes | GCS HMAC secret |
| `S3_ENDPOINT_URL` | Yes | `https://storage.googleapis.com` |

**Remove old VM secrets** (`SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`, `DEPLOY_PATH`) — no longer used.

### Service account roles

The deploy service account needs:

- `roles/run.admin`
- `roles/artifactregistry.writer`
- `roles/cloudsql.client`
- `roles/iam.serviceAccountUser`
- `roles/storage.admin` (bucket setup; runtime uses HMAC keys)

---

## Part 3 — How CI/CD works

### Branches

| Branch | Role |
|--------|------|
| `main` | CI on push/PR |
| `stage` | **Deploy branch** — CI then Cloud Run deploy |

### CI (`.github/workflows/ci.yml`)

Unit tests + Docker build on every push/PR to `main` or `stage`.

### Deploy (`.github/workflows/deploy.yml`)

Runs when CI **succeeds** on push to **`stage`**, or via **Run workflow** (manual).

Steps:

1. Build Docker image → push to `{REGION}-docker.pkg.dev/{PROJECT}/rag/rag-document-processor:{sha}`
2. Deploy **`rag-api`** — public HTTPS, port 8000, Cloud SQL attached
3. Deploy **`rag-worker`** — internal, Celery, `min-instances: 1`, no CPU throttling
4. Health check `GET /api/v1/health`

---

## Part 4 — After first deploy

### API URL

```bash
gcloud run services describe rag-api \
  --region us-central1 \
  --format='value(status.url)'
```

Open **`{URL}/docs`** in a browser (HTTPS, no firewall rules needed).

Share this URL with integrators — see [API_INTEGRATION.md](./API_INTEGRATION.md).

### Create a client API key

From **Cloud Shell** or any machine that can reach Cloud SQL:

```bash
# Clone repo, set DATABASE_URL to Cloud SQL (public IP + authorized networks, or Cloud Shell proxy)
uv sync
uv run python scripts/create_api_key.py "production client"
```

Or connect via Cloud SQL Auth Proxy locally.

---

## Part 5 — Day-to-day workflow

1. Merge changes into **`stage`**
2. GitHub **CI** runs, then **Deploy**
3. Check Actions log for `API URL:` and `Health check passed`
4. Verify `https://….run.app/docs`

Manual redeploy: **Actions → Deploy → Run workflow**

---

## Troubleshooting

| Issue | Check |
|-------|--------|
| Deploy auth fails | `GCP_SA_KEY` valid JSON; SA has required roles |
| API crash loop | Cloud Run logs: `gcloud run services logs read rag-api --region REGION` |
| `API_KEY_ADMIN_SECRET is required` | Secret set in GitHub staging environment |
| `EMBEDDING_DIMENSIONS` parse error | Omit empty `EMBEDDING_DIMENSIONS` in secrets |
| Jobs stay `pending` | Worker logs: `gcloud run services logs read rag-worker --region REGION` |
| Upload errors | GCS bucket + HMAC keys; `S3_BUCKET_NAME` correct |
| DB connection errors | `DATABASE_URL` uses `/cloudsql/CONNECTION_NAME`; Cloud SQL attached on service |

### View logs

```bash
gcloud run services logs read rag-api --region us-central1 --limit 50
gcloud run services logs read rag-worker --region us-central1 --limit 50
```

### Cost tips

- API: `min-instances: 0` (scales to zero when idle)
- Worker: `min-instances: 1` (required for Celery — main ongoing cost)
- Cloud SQL `db-f1-micro` for dev/staging
- Stop/delete unused VM if migrating from legacy deploy

---

## Local development

Unchanged — use `docker compose up` for local Postgres/Redis/MinIO and run API + worker locally. See [ONBOARDING.md](./ONBOARDING.md).

`docker-compose.prod.yml` remains for **legacy VM** testing only.

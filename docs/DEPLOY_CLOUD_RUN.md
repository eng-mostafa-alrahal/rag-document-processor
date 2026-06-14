# Step-by-step deploy guide — Cloud Run + GitHub Actions

This guide walks you through **first-time production deployment** from zero to a working HTTPS API on Google Cloud Run.

**Time:** ~45–90 minutes (mostly waiting for Cloud SQL to provision).

**What you will have at the end:**

- Public API at `https://rag-api-….run.app/docs`
- Celery worker processing jobs in the background
- Postgres on Cloud SQL, Redis on Redis Cloud, uploads on GCS
- Automatic deploys when you push to the `stage` branch

---

## Before you start — checklist

Gather these before Step 1:

| Item | Where to get it |
|------|-----------------|
| Google account + billing enabled | [console.cloud.google.com](https://console.cloud.google.com) |
| GitHub repo access (admin) | Your fork or `eng-mostafa-alrahal/rag-document-processor` |
| OpenAI API key | [platform.openai.com](https://platform.openai.com) |
| Redis Cloud account (free tier OK) | [redis.io/cloud](https://redis.io/cloud/) |
| `gcloud` CLI installed | [Install guide](https://cloud.google.com/sdk/docs/install) |

Pick values now and write them down (you will reuse them):

```text
GCP_PROJECT_ID     = my-rag-project-123
GCP_REGION         = us-central1
SQL_RAG_PASSWORD   = (long random password for DB user "rag")
API_KEY_ADMIN_SECRET = (long random string for admin API key management)
```

---

## Architecture (what we are building)

```text
GitHub push to stage
       │
       ├─ CI (tests + docker build)
       └─ Deploy workflow
              │
              ├─ Build image → Artifact Registry
              ├─ Cloud Run: rag-api     (public HTTPS)
              └─ Cloud Run: rag-worker  (Celery, always on)
                     │
                     ├─ Cloud SQL (Postgres)
                     ├─ Redis Cloud (Celery + streams)
                     └─ GCS bucket (file uploads)
```

---

## Phase 1 — Google Cloud (one-time)

### Step 1 — Create a GCP project

1. Open [Google Cloud Console](https://console.cloud.google.com).
2. Click the project dropdown (top bar) → **New project**.
3. Name it (e.g. `rag-document-processor`) → **Create**.
4. Select the new project.
5. Go to **Billing** → link a billing account (required for Cloud Run and Cloud SQL).

Note your **Project ID** (not display name). Example: `rag-doc-processor-123`.

---

### Step 2 — Install and log in to gcloud

**Windows (PowerShell):**

```powershell
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

**Mac / Linux / Git Bash:**

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

Verify:

```bash
gcloud config get-value project
```

---

### Step 3 — Run the GCP setup script (recommended)

This script enables APIs, creates Artifact Registry, Cloud SQL, a GCS bucket, and a deploy service account.

**Mac / Linux / Git Bash:**

```bash
export GCP_PROJECT_ID=YOUR_PROJECT_ID
export GCP_REGION=us-central1
export SQL_ROOT_PASSWORD='choose-a-strong-root-password'
export SQL_RAG_PASSWORD='choose-a-strong-rag-password'

chmod +x scripts/setup-gcp-cloudrun.sh
./scripts/setup-gcp-cloudrun.sh
```

**Windows PowerShell** (run from repo root; use Git Bash for the script, or run commands manually in Step 3b):

```powershell
$env:GCP_PROJECT_ID = "YOUR_PROJECT_ID"
$env:GCP_REGION = "us-central1"
$env:SQL_ROOT_PASSWORD = "choose-a-strong-root-password"
$env:SQL_RAG_PASSWORD = "choose-a-strong-rag-password"

bash scripts/setup-gcp-cloudrun.sh
```

The script prints:

- **Cloud SQL connection name** → save for GitHub secret `CLOUD_SQL_CONNECTION_NAME`
- **GCS bucket name** → save for `S3_BUCKET_NAME`
- **Service account JSON key file** → `gcp-github-deploy-key.json` → contents go in GitHub secret `GCP_SA_KEY`

> **Security:** Never commit `gcp-github-deploy-key.json`. Add it to `.gitignore` if needed.

---

### Step 3b — Manual GCP setup (if you skip the script)

<details>
<summary>Click to expand manual commands</summary>

Replace `YOUR_PROJECT_ID`, `us-central1`, and passwords.

```bash
gcloud config set project YOUR_PROJECT_ID

gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  sqladmin.googleapis.com storage.googleapis.com iam.googleapis.com cloudbuild.googleapis.com

gcloud artifacts repositories create rag \
  --repository-format=docker --location=us-central1

gcloud sql instances create rag-sql \
  --database-version=POSTGRES_16 \
  --edition=enterprise \
  --tier=db-f1-micro \
  --region=us-central1 --root-password='ROOT_PASSWORD'

gcloud sql databases create rag --instance=rag-sql
gcloud sql users create rag --instance=rag-sql --password='RAG_PASSWORD'

gcloud storage buckets create gs://YOUR_PROJECT_ID-rag-uploads --location=us-central1

gcloud iam service-accounts create rag-github-deploy \
  --display-name="GitHub Actions Cloud Run deploy"

SA=rag-github-deploy@YOUR_PROJECT_ID.iam.gserviceaccount.com
for ROLE in roles/run.admin roles/artifactregistry.writer roles/cloudsql.client \
  roles/iam.serviceAccountUser roles/storage.admin; do
  gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:$SA" --role="$ROLE" --quiet
done

gcloud iam service-accounts keys create gcp-github-deploy-key.json --iam-account="$SA"
```

Get connection name:

```bash
gcloud sql instances describe rag-sql --format='value(connectionName)'
# Example: YOUR_PROJECT_ID:us-central1:rag-sql
```

</details>

---

### Step 4 — Create GCS HMAC keys (for file uploads)

Cloud Run stores uploads in **Google Cloud Storage** using S3-compatible HMAC keys.

1. Console → **Cloud Storage** → **Settings** (left sidebar) → **Interoperability**.
2. If prompted, click **Enable interoperability access**.
3. Under **Access keys for service accounts**, click **Create a key for a service account**.
4. Choose any service account (e.g. your deploy SA or the default compute SA).
5. Save the **Access key** and **Secret** — shown once.

You will add these to GitHub as:

- `S3_ACCESS_KEY_ID` = Access key
- `S3_SECRET_ACCESS_KEY` = Secret
- `S3_ENDPOINT_URL` = `https://storage.googleapis.com`
- `S3_BUCKET_NAME` = bucket from setup script (e.g. `YOUR_PROJECT_ID-rag-uploads`)

---

### Step 5 — Build your database URLs

Use the **Cloud SQL connection name** from Step 3 and the **rag user password** you chose.

Format (replace `PASSWORD` and `CONNECTION_NAME`):

```text
postgresql+asyncpg://rag:PASSWORD@/rag?host=/cloudsql/CONNECTION_NAME
postgresql://rag:PASSWORD@/rag?host=/cloudsql/CONNECTION_NAME
```

**Example** (password `MyStr0ng!Pass`, connection `my-project:us-central1:rag-sql`):

```text
postgresql+asyncpg://rag:MyStr0ng!Pass@/rag?host=/cloudsql/my-project:us-central1:rag-sql
postgresql://rag:MyStr0ng!Pass@/rag?host=/cloudsql/my-project:us-central1:rag-sql
```

> Special characters in passwords (`@`, `#`, `!`) must be URL-encoded in the connection string, or use a password without those characters.

These become GitHub secrets `DATABASE_URL` and `DATABASE_URL_SYNC`.

---

## Phase 2 — Redis Cloud (one-time)

You already use Redis Cloud locally — production uses the same pattern.

### Step 6 — Create or reuse a Redis Cloud database

1. Log in to [Redis Cloud](https://redis.io/cloud/).
2. Create a database (or reuse an existing one).
3. Copy the **public** connection URL. It looks like:
   ```text
   rediss://default:PASSWORD@redis-12345.c123.us-east-1-4.ec2.redns.redis-cloud.com:12345
   ```
4. Build three URLs (same host, different DB index if your plan allows):

| Secret | Example |
|--------|---------|
| `REDIS_URL` | `rediss://default:PASS@host:port/0` |
| `CELERY_BROKER_URL` | `rediss://default:PASS@host:port/1` |
| `CELERY_RESULT_BACKEND` | `rediss://default:PASS@host:port/2` |

If your Redis plan only supports DB `0`, use `/0` for all three.

---

## Phase 3 — GitHub secrets (one-time)

### Step 7 — Create the `staging` environment

1. Open your repo on GitHub.
2. **Settings** → **Environments** → **New environment**.
3. Name it exactly: **`staging`** (the deploy workflow uses this name).
4. Optional: add **Required reviewers** for production safety.

---

### Step 8 — Add all secrets to `staging`

Go to **Settings → Environments → staging → Add secret**.

Add **every** secret below. Copy names exactly (case-sensitive).

#### GCP / deploy

| Secret name | Value | How to get it |
|-------------|-------|---------------|
| `GCP_PROJECT_ID` | `my-project-123` | Step 1 |
| `GCP_REGION` | `us-central1` | Your chosen region |
| `GCP_SA_KEY` | Full JSON file contents | `gcp-github-deploy-key.json` from Step 3 |
| `CLOUD_SQL_CONNECTION_NAME` | `project:region:rag-sql` | Output of setup script |

#### Database

| Secret name | Value |
|-------------|-------|
| `DATABASE_URL` | Async URL from Step 5 |
| `DATABASE_URL_SYNC` | Sync URL from Step 5 |

#### Redis

| Secret name | Value |
|-------------|-------|
| `REDIS_URL` | From Step 6 |
| `CELERY_BROKER_URL` | From Step 6 |
| `CELERY_RESULT_BACKEND` | From Step 6 |

#### Application

| Secret name | Value |
|-------------|-------|
| `API_KEY_ADMIN_SECRET` | Long random string (you choose) |
| `OPENAI_API_KEY` | `sk-...` from OpenAI |

Optional (add only if you use them):

| Secret name | When needed |
|-------------|-------------|
| `JINA_API_KEY` | Jina embedder instead of OpenAI |
| `LLAMA_CLOUD_API_KEY` | Cloud PDF/DOCX parsing |

#### Storage (GCS)

| Secret name | Value |
|-------------|-------|
| `S3_BUCKET_NAME` | e.g. `my-project-rag-uploads` |
| `S3_ACCESS_KEY_ID` | HMAC access key from Step 4 |
| `S3_SECRET_ACCESS_KEY` | HMAC secret from Step 4 |
| `S3_ENDPOINT_URL` | `https://storage.googleapis.com` |

> **Tip:** See [`.env.cloudrun.example`](../.env.cloudrun.example) for a copy-paste checklist of secret names.

---

### Step 9 — Remove old VM secrets (if migrating)

If you previously deployed to a VM, delete these from GitHub (no longer used):

- `SSH_HOST`
- `SSH_USER`
- `SSH_PRIVATE_KEY`
- `DEPLOY_PATH`

---

## Phase 4 — First deploy

### Step 10 — Push the Cloud Run code to `stage`

If your Cloud Run commit is not on GitHub yet:

```bash
git checkout stage
git push origin stage
```

If you already pushed, trigger deploy manually (Step 11).

---

### Step 11 — Run the Deploy workflow

**Option A — Automatic (push to `stage`):**

1. Push any commit to `stage`.
2. **Actions** tab → wait for **CI** to finish green.
3. **Deploy** workflow starts automatically after CI succeeds.

**Option B — Manual (no new commit):**

1. GitHub → **Actions** → **Deploy**.
2. **Run workflow** → branch **`stage`** → **Run workflow**.

---

### Step 12 — Watch the deploy log

Open the running **Deploy** job. It should:

1. Authenticate to GCP
2. Build and push Docker image to Artifact Registry
3. Deploy `rag-api` to Cloud Run
4. Deploy `rag-worker` to Cloud Run
5. Print **API URL** and **Health check passed**

Expected log lines:

```text
API URL: https://rag-api-xxxxxxxx-uc.a.run.app
Docs:    https://rag-api-xxxxxxxx-uc.a.run.app/docs
Health check passed
```

If the job fails, jump to [Troubleshooting](#troubleshooting).

---

### Step 13 — Verify in the browser

1. Open the **API URL** from the log + `/docs`
   ```text
   https://rag-api-xxxxxxxx-uc.a.run.app/docs
   ```
2. Expand **GET /api/v1/health** → **Try it out** → **Execute**.
3. You should see `200` with a healthy response.

No firewall rules needed — Cloud Run serves HTTPS by default.

---

## Phase 5 — After first deploy

### Step 14 — Create a client API key

You need a database connection to run the bootstrap script. Easiest path: **Cloud Shell** in GCP Console.

1. Console → click **Activate Cloud Shell** (top right).
2. Clone the repo and install deps:

```bash
git clone -b stage https://github.com/eng-mostafa-alrahal/rag-document-processor.git
cd rag-document-processor

# Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

uv sync
```

3. Set env vars (replace with your real values):

```bash
export DATABASE_URL_SYNC="postgresql://rag:PASSWORD@/rag?host=/cloudsql/PROJECT:REGION:rag-sql"
export API_KEY_ADMIN_SECRET="your-admin-secret-from-github"
```

4. Run Cloud SQL Auth Proxy in Cloud Shell (or use public IP + authorized networks):

```bash
# Download proxy
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.3/cloud-sql-proxy.linux.amd64
chmod +x cloud-sql-proxy

# In background — replace CONNECTION_NAME
./cloud-sql-proxy CONNECTION_NAME &
sleep 3

# Use TCP locally instead of socket for the script
export DATABASE_URL_SYNC="postgresql://rag:PASSWORD@127.0.0.1:5432/rag"
uv run python scripts/create_api_key.py "production client"
```

5. **Copy the API key** from the output — it is shown **once**.

**Alternative:** Run the same script on your laptop with [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/connect-auth-proxy) pointing at your instance.

---

### Step 15 — Smoke test ingest

Replace `YOUR_API_KEY` and `YOUR_API_URL`:

```bash
curl -X POST "https://rag-api-xxxxxxxx-uc.a.run.app/api/v1/ingest/text" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from Cloud Run", "options": {}}'
```

Response includes `job_id`. Poll status:

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  "https://rag-api-xxxxxxxx-uc.a.run.app/api/v1/jobs/JOB_ID"
```

When `status` is `completed`, fetch results:

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  "https://rag-api-xxxxxxxx-uc.a.run.app/api/v1/jobs/JOB_ID/results"
```

Share the base URL and integration details with other teams: [API_INTEGRATION.md](./API_INTEGRATION.md).

---

## Day-to-day deploys (after setup)

Every time you want to update production:

```bash
git checkout stage
git merge main          # or commit directly on stage
git push origin stage
```

1. **CI** runs (tests + Docker build).
2. **Deploy** runs automatically when CI passes.
3. Check Actions log for `Health check passed`.

Manual redeploy without a new commit: **Actions → Deploy → Run workflow**.

---

## Quick reference — all GitHub secrets

| Secret | Required |
|--------|----------|
| `GCP_PROJECT_ID` | Yes |
| `GCP_REGION` | Yes |
| `GCP_SA_KEY` | Yes |
| `CLOUD_SQL_CONNECTION_NAME` | Yes |
| `DATABASE_URL` | Yes |
| `DATABASE_URL_SYNC` | Yes |
| `REDIS_URL` | Yes |
| `CELERY_BROKER_URL` | Yes |
| `CELERY_RESULT_BACKEND` | Yes |
| `API_KEY_ADMIN_SECRET` | Yes |
| `OPENAI_API_KEY` | Yes* |
| `S3_BUCKET_NAME` | Yes |
| `S3_ACCESS_KEY_ID` | Yes |
| `S3_SECRET_ACCESS_KEY` | Yes |
| `S3_ENDPOINT_URL` | Yes |
| `JINA_API_KEY` | Optional |
| `LLAMA_CLOUD_API_KEY` | Optional |

\*Or `JINA_API_KEY` if using Jina embedder.

---

## Troubleshooting

| Symptom | What to check |
|---------|---------------|
| Deploy fails at **Authenticate to Google Cloud** | `GCP_SA_KEY` is valid JSON (entire file pasted, including `{` and `}`) |
| Deploy fails at **docker push** | Service account has `roles/artifactregistry.writer`; Artifact Registry repo `rag` exists in `GCP_REGION` |
| Deploy fails at **gcloud run deploy** | `CLOUD_SQL_CONNECTION_NAME` correct; SA has `roles/run.admin` and `roles/cloudsql.client` |
| Health check fails | Cloud Run logs: `gcloud run services logs read rag-api --region us-central1 --limit 50` |
| API crash: `API_KEY_ADMIN_SECRET is required` | Secret missing in **staging** environment (not repo-level only) |
| Jobs stay `pending` | Worker not running — check `gcloud run services logs read rag-worker --region us-central1` |
| Upload / S3 errors | HMAC keys correct; bucket name matches `S3_BUCKET_NAME` |
| DB connection errors | `DATABASE_URL` uses `/cloudsql/CONNECTION_NAME`; Cloud SQL instance attached on both services |

### View logs

```bash
gcloud run services logs read rag-api --region us-central1 --limit 50
gcloud run services logs read rag-worker --region us-central1 --limit 50
```

### Get API URL anytime

```bash
gcloud run services describe rag-api \
  --region us-central1 \
  --format='value(status.url)'
```

---

## Cost tips

| Resource | Typical staging cost |
|----------|---------------------|
| Cloud Run API | Scales to zero when idle |
| Cloud Run worker | Always on (`min-instances: 1`) — main ongoing cost |
| Cloud SQL `db-f1-micro` | ~$7–10/month |
| Redis Cloud | Free tier often sufficient |
| GCS | Pennies for small uploads |

Delete the old GCP VM if you migrated from the legacy SSH deploy.

---

## Local development

Unchanged — use Docker Compose locally. See [ONBOARDING.md](./ONBOARDING.md).

Legacy VM stack: `docker-compose.prod.yml` (deprecated).

Legacy VM docs: [DEPLOY_GCP.md](./DEPLOY_GCP.md).

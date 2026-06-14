#!/usr/bin/env bash
# One-time GCP setup for Cloud Run deploy (run locally with gcloud CLI).
# See docs/DEPLOY_CLOUD_RUN.md for full instructions.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-rag-sql}"
GCS_BUCKET="${GCS_BUCKET:-${PROJECT_ID}-rag-uploads}"
SA_NAME="${GCP_DEPLOY_SA:-rag-github-deploy}"
AR_REPO="rag"

echo "Project: $PROJECT_ID  Region: $REGION"

gcloud config set project "$PROJECT_ID"

echo "Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com \
  cloudbuild.googleapis.com

echo "Creating Artifact Registry repo (ignore if exists)..."
gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker \
  --location="$REGION" 2>/dev/null || true

echo "Creating Cloud SQL Postgres (ignore if exists)..."
gcloud sql instances create "$SQL_INSTANCE" \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region="$REGION" \
  --root-password="${SQL_ROOT_PASSWORD:?Set SQL_ROOT_PASSWORD}" 2>/dev/null || true

gcloud sql databases create rag --instance="$SQL_INSTANCE" 2>/dev/null || true
gcloud sql users create rag \
  --instance="$SQL_INSTANCE" \
  --password="${SQL_RAG_PASSWORD:?Set SQL_RAG_PASSWORD}" 2>/dev/null || true

CONNECTION_NAME=$(gcloud sql instances describe "$SQL_INSTANCE" --format='value(connectionName)')
echo "Cloud SQL connection: $CONNECTION_NAME"

echo "Creating GCS bucket (ignore if exists)..."
gcloud storage buckets create "gs://${GCS_BUCKET}" --location="$REGION" 2>/dev/null || true

echo "Creating deploy service account (ignore if exists)..."
gcloud iam service-accounts create "$SA_NAME" \
  --display-name="GitHub Actions Cloud Run deploy" 2>/dev/null || true

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

for ROLE in roles/run.admin roles/artifactregistry.writer roles/cloudsql.client roles/iam.serviceAccountUser roles/storage.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$ROLE" \
    --quiet >/dev/null
done

KEY_FILE="${GCP_SA_KEY_FILE:-./gcp-github-deploy-key.json}"
gcloud iam service-accounts keys create "$KEY_FILE" --iam-account="$SA_EMAIL"

cat <<EOF

=== Next steps ===

1. Add GitHub Environment secrets (staging):

   GCP_PROJECT_ID=$PROJECT_ID
   GCP_REGION=$REGION
   GCP_SA_KEY=<contents of $KEY_FILE>
   CLOUD_SQL_CONNECTION_NAME=$CONNECTION_NAME

   DATABASE_URL=postgresql+asyncpg://rag:YOUR_PASSWORD@/rag?host=/cloudsql/$CONNECTION_NAME
   DATABASE_URL_SYNC=postgresql://rag:YOUR_PASSWORD@/rag?host=/cloudsql/$CONNECTION_NAME

   REDIS_URL=<your Redis Cloud URL>
   CELERY_BROKER_URL=<redis url db 1>
   CELERY_RESULT_BACKEND=<redis url db 2>

   API_KEY_ADMIN_SECRET=<random>
   OPENAI_API_KEY=sk-...

   S3_BUCKET_NAME=$GCS_BUCKET
   S3_ENDPOINT_URL=https://storage.googleapis.com
   S3_ACCESS_KEY_ID=<GCS HMAC access key>
   S3_SECRET_ACCESS_KEY=<GCS HMAC secret>

2. Push to stage branch or run GitHub Actions Deploy workflow.

3. After first deploy, create an API key (Cloud Run Job or local):
   gcloud run jobs execute rag-create-api-key --region $REGION   # optional future job
   Or run scripts/create_api_key.py against Cloud SQL from Cloud Shell.

API URL after deploy:
   gcloud run services describe rag-api --region $REGION --format='value(status.url)'

EOF

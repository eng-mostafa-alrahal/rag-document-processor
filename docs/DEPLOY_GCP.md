# Deploy on GCP (budget VM) + GitHub Actions CI/CD

This guide deploys the full stack on **one small GCP VM** (~$0/month on the free-tier `e2-micro`) and uses **GitHub Actions** to test every PR and auto-deploy `main`.

## Architecture

```
GitHub (push/PR)
    │
    ├─ CI workflow ──► unit tests + Docker build
    │
    └─ Deploy workflow (main only) ──SSH──► GCP VM
                                              ├─ postgres
                                              ├─ redis
                                              ├─ minio
                                              ├─ api :8000
                                              └─ worker
```

## Part 1 — Create the GCP VM (Console UI)

1. [Google Cloud Console](https://console.cloud.google.com) → create/select a project.
2. **Billing** → set a **budget alert** (e.g. $5).
3. **APIs & Services → Library** → enable **Compute Engine API**.
4. **Compute Engine → VM instances → Create instance**
   - Name: `rag-server`
   - Region: `us-central1` (or `us-west1` / `us-east1` for Always Free `e2-micro`)
   - Machine type: **e2-micro**
   - Boot disk: Ubuntu 22.04 LTS, 20 GB
   - Firewall: allow **HTTP** and **HTTPS**
5. Create the VM and note the **External IP**.

### Firewall for the API (port 8000)

**VPC network → Firewall → Create rule**

- Name: `allow-api-8000`
- Targets: All instances in the network
- Source: `0.0.0.0/0` (or your home IP for tighter security)
- Protocol: `tcp:8000`

API docs after deploy: `http://YOUR_VM_IP:8000/docs`

## Part 2 — Prepare the VM (browser SSH)

On the VM list, click **SSH** next to your instance.

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER"
```

Close SSH, open a **new** SSH session, then:

```bash
git clone -b stage https://github.com/YOUR_ORG/rag-document-processor.git
cd rag-document-processor

cp .env.example .env
nano .env
```

Deployments track the **`stage`** branch. Use `main` for stable code; merge into `stage` when you want the VM updated.

Set at least (compose overrides DB/Redis/MinIO hostnames; secrets stay in `.env`):

```env
API_KEY_ADMIN_SECRET=long-random-string
OPENAI_API_KEY=sk-...
# JINA_API_KEY=...
# LLAMA_CLOUD_API_KEY=...
```

After the stack is up, mint a client API key (shown once):

```bash
docker compose -f docker-compose.prod.yml exec api python scripts/create_api_key.py "first client"
```

Postgres, Redis, and MinIO are **not** installed on the VM separately — `docker-compose.prod.yml` starts them as containers when you deploy. You only need Docker and git on the host.

First manual deploy:

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

Create the MinIO bucket once (uploads). From the VM, after the stack is up:

```bash
NETWORK=$(docker network ls --format '{{.Name}}' | grep rag-document-processor | head -1)
docker run --rm --network "$NETWORK" minio/mc alias set local http://minio:9000 minioadmin minioadmin
docker run --rm --network "$NETWORK" minio/mc mb local/rag-uploads --ignore-existing
```

## Part 3 — GitHub Actions secrets

In your GitHub repo: **Settings → Secrets and variables → Actions**.

Create an **Environment** named `staging` (**Settings → Environments → New**). Add secrets there (recommended) or at repo level. Deploys run from the **`stage`** branch into this environment.

| Secret | Example | Description |
|--------|---------|-------------|
| `SSH_HOST` | `34.12.34.56` | VM external IP |
| `SSH_USER` | `your_username` | Linux user on the VM (from browser SSH) |
| `SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH PRIVATE KEY-----...` | Private key for deploy (see below) |
| `DEPLOY_PATH` | `/home/your_username/rag-document-processor` | Absolute path to the repo on the VM |

Optional: `SSH_PORT` if not using 22.

### Deploy SSH key (recommended)

On your **local machine**:

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f github_deploy_key -N ""
```

On the **VM** (append the public key):

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "PASTE_CONTENTS_OF_github_deploy_key.pub" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

In **GitHub**, set `SSH_PRIVATE_KEY` to the full contents of `github_deploy_key` (private file).

### Private GitHub repo on the VM

Use a **deploy key** so `git fetch` on the VM works:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub   # add as Deploy key in GitHub repo settings (read-only)
git clone -b stage git@github.com:YOUR_ORG/rag-document-processor.git
```

## Part 4 — How CI/CD works

### Branches

| Branch | Role |
|--------|------|
| `main` | Default branch; CI runs on push/PR. Workflow definitions live here. |
| `stage` | **Deploy branch** — pushes here deploy to the GCP VM after CI passes. |

### CI (`.github/workflows/ci.yml`)

Runs on every **push** and **pull request** to `main` or `stage`:

1. `uv sync --extra dev`
2. `uv run pytest tests/unit -q`
3. `docker build` (ensures the production image builds)

### Deploy (`.github/workflows/deploy.yml`)

Runs when:

- CI **succeeds** on a push to **`stage`**, or
- You click **Run workflow** manually (`workflow_dispatch`)

Steps over SSH:

```bash
cd $DEPLOY_PATH
git fetch origin stage && git checkout stage && git reset --hard origin/stage
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
```

Watch runs under **Actions** in GitHub.

## Part 5 — Day-to-day workflow

1. Open a PR into `stage` (or `main`) → CI runs tests.
2. Merge to **`stage`** → CI runs → Deploy updates the VM.
3. Check `http://YOUR_VM_IP:8000/docs`.

If the VM was cloned from `main`, switch it once:

```bash
cd ~/rag-document-processor
git fetch origin stage
git checkout stage
```

Manual deploy on the VM:

```bash
cd ~/rag-document-processor
./scripts/deploy.sh
```

## Part 6 — Access Postgres, Redis, and MinIO from your laptop

Production compose keeps Postgres and Redis **internal** (not on the public internet). To browse them with DBeaver, Redis Insight, or the MinIO console, use the optional debug override plus an SSH tunnel.

### On the VM (enable localhost ports)

```bash
cd ~/rag-document-processor
docker compose -f docker-compose.prod.yml -f docker-compose.debug.yml up -d
```

`docker-compose.debug.yml` binds services to `127.0.0.1` on the VM only — still not reachable from the internet.

### On your laptop (SSH tunnel)

Windows PowerShell or terminal:

```bash
ssh -L 5432:localhost:5432 -L 6379:localhost:6379 -L 9001:localhost:9001 USER@VM_IP
```

Or with gcloud:

```bash
gcloud compute ssh rag-server --zone=YOUR_ZONE -- -L 5432:localhost:5432 -L 6379:localhost:6379 -L 9001:localhost:9001
```

Keep that session open, then connect GUI tools to **localhost**:

| Service | Host | Port | Credentials |
|---------|------|------|-------------|
| Postgres | `localhost` | `5432` | user `rag`, password `rag`, database `rag` |
| Redis | `localhost` | `6379` | no password |
| MinIO console | `http://localhost:9001` | | `minioadmin` / `minioadmin`, bucket `rag-uploads` |

**Security:** never open ports `5432` or `6379` in the GCP firewall. SSH tunnel only.

### CLI on the VM (no tunnel)

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U rag -d rag
docker compose -f docker-compose.prod.yml exec redis redis-cli
```

## Cost tips

- Use **e2-micro** in a free-tier region.
- **Stop** the VM when not testing (**Compute Engine → Stop**).
- Set billing budget alerts.
- Avoid Cloud SQL + Memorystore until you need managed services.

## Troubleshooting

| Issue | Check |
|-------|--------|
| Deploy fails SSH | `SSH_HOST`, `SSH_USER`, key in `authorized_keys`, firewall allows port 22 |
| API up, jobs pending | `docker compose -f docker-compose.prod.yml logs worker` |
| DB errors | `docker compose -f docker-compose.prod.yml logs api` (migrations on startup) |
| Upload errors | MinIO bucket `rag-uploads` exists |

## Files added for deployment

| File | Purpose |
|------|---------|
| `docker-compose.prod.yml` | Full production stack on one VM |
| `docker-compose.debug.yml` | Optional localhost ports for SSH-tunnel access from your laptop |
| `.github/workflows/ci.yml` | Tests + Docker build |
| `.github/workflows/deploy.yml` | SSH deploy after CI |
| `scripts/deploy.sh` | Manual deploy helper on the VM |

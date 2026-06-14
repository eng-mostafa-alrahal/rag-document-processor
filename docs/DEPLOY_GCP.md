# Deploy on GCP — legacy VM (deprecated)

> **Use Cloud Run instead:** [DEPLOY_CLOUD_RUN.md](./DEPLOY_CLOUD_RUN.md)  
> GitHub Actions now deploys to **Cloud Run**, not SSH to a VM.

---

## Legacy VM deploy (deprecated)

The sections below describe the old **single VM + docker compose** setup. They are kept for reference if you still have a VM running.

### What changed

| Before (VM) | Now (Cloud Run) |
|---------------|-----------------|
| SSH deploy via `appleboy/ssh-action` | `gcloud run deploy` |
| Postgres/Redis/MinIO on VM | Cloud SQL + Redis Cloud + GCS |
| `http://VM_IP:8000` | `https://….run.app` |
| Secrets in VM `.env` | GitHub Environment secrets |
| Firewall port 8000 | Not needed (HTTPS by default) |

### Shut down the old VM

1. GCP Console → **Compute Engine** → stop/delete the VM
2. Remove GitHub secrets: `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`, `DEPLOY_PATH`
3. Follow [DEPLOY_CLOUD_RUN.md](./DEPLOY_CLOUD_RUN.md) for Cloud Run secrets

---

<details>
<summary>Original VM deploy guide (archived)</summary>

See git history for the full VM + SSH + `docker-compose.prod.yml` documentation, or the archived content in commit before Cloud Run migration.

Quick reference files (legacy only):

- `docker-compose.prod.yml`
- `docker-compose.debug.yml`
- `scripts/deploy.sh`

</details>

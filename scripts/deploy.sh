#!/usr/bin/env bash
# Run on the GCP VM after git pull (also invoked by GitHub Actions deploy workflow).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example to .env and set secrets first." >&2
  exit 1
fi

docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
docker compose -f docker-compose.prod.yml ps

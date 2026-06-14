#!/bin/sh
# Cloud Run requires a process listening on $PORT for startup/liveness probes.
# Celery does not serve HTTP, so we run the worker in the background and a
# tiny health server in the foreground.
set -eu

PORT="${PORT:-8080}"

celery -A rag_document_processor.workers.celery_app worker -l info --concurrency=1 &
WORKER_PID=$!

cleanup() {
  kill "$WORKER_PID" 2>/dev/null || true
}
trap cleanup INT TERM

export WORKER_PID
exec python - <<'PY'
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

worker_pid = int(os.environ["WORKER_PID"])
port = int(os.environ.get("PORT", "8080"))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            os.kill(worker_pid, 0)
        except OSError:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"celery worker not running")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, fmt: str, *args: object) -> None:
        pass


HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
PY

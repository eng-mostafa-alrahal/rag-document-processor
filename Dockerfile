FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -e . \
    && sed -i 's/\r$//' scripts/*.sh \
    && chmod +x scripts/cloudrun_celery_worker.sh

EXPOSE 8000
# Cloud Run sets PORT (default 8080); local/docker-compose uses 8000.
CMD ["sh", "-c", "exec uvicorn rag_document_processor.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir src"]

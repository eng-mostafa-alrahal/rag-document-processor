FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "rag_document_processor.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]

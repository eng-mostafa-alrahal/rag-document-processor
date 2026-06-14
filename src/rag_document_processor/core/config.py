from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from rag_document_processor.core.embedding_dimensions import validate_embedding_dimensions
from rag_document_processor.core.ingest_embedding_options import resolve_ingest_embedding_options

# LlamaCloud parse tiers (API + env); keep in sync with `Settings.llama_parse_tier`.
LLAMA_PARSE_TIER_CHOICES: frozenset[str] = frozenset(
    ("fast", "cost_effective", "agentic", "agentic_plus")
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="rag-document-processor", alias="APP_NAME")
    env: str = Field(default="dev", alias="ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    database_url_sync: str | None = Field(default=None, alias="DATABASE_URL_SYNC")
    database_auto_migrate: bool = Field(default=False, alias="DATABASE_AUTO_MIGRATE")
    database_auto_create: bool = Field(
        default=False,
        alias="DATABASE_AUTO_CREATE",
        description="When true, create the target Postgres database if missing (dev convenience; needs CREATEDB or superuser).",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_stream_db: int = Field(default=0, alias="REDIS_STREAM_DB")
    redis_stream_maxlen: int = Field(default=10_000, alias="REDIS_STREAM_MAXLEN")

    celery_broker_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND")
    celery_task_default_queue: str = Field(default="ingest", alias="CELERY_TASK_DEFAULT_QUEUE")

    api_key_admin_secret: str | None = Field(
        default=None,
        alias="API_KEY_ADMIN_SECRET",
        description=(
            "Shared secret that protects the API key management endpoints "
            "(create/list/revoke). Send it as the `X-Admin-Secret` header. "
            "Required outside dev/test."
        ),
    )

    storage_backend: Literal["local", "s3"] = Field(default="local", alias="STORAGE_BACKEND")
    local_storage_path: str = Field(default="./data/uploads", alias="LOCAL_STORAGE_PATH")
    s3_endpoint_url: str | None = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_access_key_id: str | None = Field(default=None, alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str | None = Field(default=None, alias="S3_SECRET_ACCESS_KEY")
    s3_bucket_name: str = Field(default="rag-uploads", alias="S3_BUCKET_NAME")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")

    max_upload_bytes: int = Field(default=20 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")
    max_url_fetch_bytes: int = Field(default=20 * 1024 * 1024, alias="MAX_URL_FETCH_BYTES")
    allowed_upload_content_types: str = Field(
        default="application/pdf,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        alias="ALLOWED_UPLOAD_CONTENT_TYPES",
    )

    embedding_pipeline: Literal["late_chunking", "chunk_then_embed"] = Field(
        default="chunk_then_embed", alias="EMBEDDING_PIPELINE"
    )
    macro_splitter: Literal["semantic", "recursive", "token_aware"] = Field(
        default="recursive", alias="MACRO_SPLITTER"
    )
    embedder_context_tokens: int = Field(default=8192, alias="EMBEDDER_CONTEXT_TOKENS")

    jina_api_key: str | None = Field(default=None, alias="JINA_API_KEY")
    jina_embedding_model: str = Field(default="jina-embeddings-v3", alias="JINA_EMBEDDING_MODEL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")

    llama_cloud_api_key: str | None = Field(default=None, alias="LLAMA_CLOUD_API_KEY")
    llama_parse_tier: Literal["fast", "cost_effective", "agentic", "agentic_plus"] = Field(
        default="agentic",
        alias="LLAMA_PARSE_TIER",
        description=(
            "Default LlamaCloud parse tier when a job omits `llama_parse_tier` "
            "(see ingest API). Per-request values override for that job only."
        ),
    )
    embedding_dimensions: int | None = Field(
        default=None,
        alias="EMBEDDING_DIMENSIONS",
        description=(
            "Default output embedding size when a job omits `embedding_dimensions` "
            "(Matryoshka / OpenAI `dimensions`). Must fit the active embedder model."
        ),
    )

    @field_validator("embedding_dimensions", mode="before")
    @classmethod
    def _empty_embedding_dimensions_as_none(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return None
        return v

    @model_validator(mode="after")
    def _dev_defaults(self) -> Settings:
        if self.env.lower() in ("dev", "development", "test"):
            if not self.database_url:
                object.__setattr__(
                    self,
                    "database_url",
                    "postgresql+asyncpg://rag:rag@localhost:5432/rag",
                )
            if not self.api_key_admin_secret:
                object.__setattr__(self, "api_key_admin_secret", "dev-only-admin-secret-change-me")
            if not self.openai_api_key:
                object.__setattr__(self, "openai_api_key", "dev-openai-placeholder-not-for-production")
        if not self.database_url:
            raise ValueError("DATABASE_URL is required outside dev/test environments")
        if not self.api_key_admin_secret:
            raise ValueError("API_KEY_ADMIN_SECRET is required outside dev/test environments")
        if "database_auto_migrate" not in self.model_fields_set:
            object.__setattr__(
                self,
                "database_auto_migrate",
                self.env.lower() in ("dev", "development", "test"),
            )
        if "database_auto_create" not in self.model_fields_set:
            object.__setattr__(
                self,
                "database_auto_create",
                self.env.lower() in ("dev", "development", "test"),
            )
        _resolved = resolve_ingest_embedding_options(
            self,
            job_embedding_pipeline=None,
            job_macro_splitter=None,
            job_embedder_provider=None,
            job_openai_embedding_model=None,
            job_jina_embedding_model=None,
        )
        validate_embedding_dimensions(
            embedder=_resolved.embedder,
            openai_embedding_model=_resolved.openai_embedding_model,
            jina_embedding_model=_resolved.jina_embedding_model,
            dim=self.embedding_dimensions,
        )
        return self

    @property
    def allowed_mime_set(self) -> set[str]:
        return {m.strip() for m in self.allowed_upload_content_types.split(",") if m.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

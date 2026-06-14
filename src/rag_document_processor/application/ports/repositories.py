from __future__ import annotations

from typing import Protocol
from uuid import UUID

from rag_document_processor.domain.entities.api_key import ApiKey
from rag_document_processor.domain.entities.job import IngestionJob, JobStatus, SourceKind


class IApiKeyRepository(Protocol):
    async def create(self, *, key_id: UUID, name: str, key_prefix: str, key_hash: str) -> ApiKey: ...

    async def get_active_by_hash(self, key_hash: str) -> ApiKey | None: ...

    async def list_all(self) -> list[ApiKey]: ...

    async def revoke(self, key_id: UUID) -> bool: ...

    async def touch_last_used(self, key_id: UUID) -> None: ...


class IJobRepository(Protocol):
    async def create(
        self,
        *,
        job_id: UUID,
        source_kind: SourceKind,
        status: JobStatus,
        blob_key: str | None = None,
        source_url: str | None = None,
        source_text: str | None = None,
        content_type: str | None = None,
        original_filename: str | None = None,
        llama_parse_tier: str | None = None,
        embedding_dimensions: int | None = None,
        embedding_pipeline: str | None = None,
        macro_splitter: str | None = None,
        embedder_provider: str | None = None,
        openai_embedding_model: str | None = None,
        jina_embedding_model: str | None = None,
    ) -> IngestionJob: ...

    async def get_by_id(self, job_id: UUID) -> IngestionJob | None: ...

    async def update_status(
        self,
        job_id: UUID,
        *,
        status: JobStatus,
        error_message: str | None = None,
    ) -> None: ...

    async def increment_chunks(self, job_id: UUID, delta: int) -> None: ...

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from rag_document_processor.domain.entities.job import IngestionJob, JobStatus, SourceKind
from rag_document_processor.domain.entities.user import User


class IUserRepository(Protocol):
    async def create(self, user: User) -> User: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...


class IJobRepository(Protocol):
    async def create(
        self,
        *,
        job_id: UUID,
        user_id: UUID,
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

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ApiKeyDTO:
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: str
    last_used_at: str | None


@dataclass(frozen=True, slots=True)
class ApiKeyCreatedDTO:
    id: UUID
    name: str
    key_prefix: str
    api_key: str
    created_at: str


@dataclass(frozen=True, slots=True)
class JobCreatedDTO:
    job_id: UUID


@dataclass(frozen=True, slots=True)
class JobStatusDTO:
    job_id: UUID
    status: str
    source_kind: str
    chunks_emitted: int
    error_message: str | None
    llama_parse_tier: str
    embedding_dimensions: int | None
    embedding_pipeline: str
    macro_splitter: str
    embedder_provider: str
    embedding_model: str
    created_at: str
    updated_at: str

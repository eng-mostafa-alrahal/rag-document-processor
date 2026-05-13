from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TokenPairDTO:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(frozen=True, slots=True)
class UserPublicDTO:
    id: UUID
    email: str


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

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class UrlIngestRequest(BaseModel):
    url: HttpUrl


class TextIngestRequest(BaseModel):
    texts: list[str] = Field(default_factory=list, min_length=1)


class JobCreatedResponse(BaseModel):
    job_id: UUID


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    source_kind: str
    chunks_emitted: int
    error_message: str | None
    created_at: str
    updated_at: str

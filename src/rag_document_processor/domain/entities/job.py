from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceKind(StrEnum):
    FILE = "file"
    URL = "url"
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class IngestionJob:
    id: UUID
    user_id: UUID
    status: JobStatus
    source_kind: SourceKind
    blob_key: str | None
    source_url: str | None
    source_text: str | None
    content_type: str | None
    original_filename: str | None
    # None => worker uses Settings.llama_parse_tier (env default).
    llama_parse_tier: str | None
    error_message: str | None
    chunks_emitted: int
    created_at: datetime
    updated_at: datetime

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

from rag_document_processor.core.config import LLAMA_PARSE_TIER_CHOICES


class UrlIngestRequest(BaseModel):
    url: HttpUrl
    llama_parse_tier: str | None = Field(
        default=None,
        description="LlamaCloud parse tier for PDF/DOCX from this URL; omit to use LLAMA_PARSE_TIER from env.",
    )

    @field_validator("llama_parse_tier")
    @classmethod
    def _validate_tier(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        t = str(v).strip()
        if t not in LLAMA_PARSE_TIER_CHOICES:
            raise ValueError(
                f"llama_parse_tier must be one of {', '.join(sorted(LLAMA_PARSE_TIER_CHOICES))}; got {t!r}"
            )
        return t


class TextIngestRequest(BaseModel):
    texts: list[str] = Field(default_factory=list, min_length=1)
    llama_parse_tier: str | None = Field(
        default=None,
        description="Reserved for consistency; plain-text jobs do not use LlamaCloud parse.",
    )

    @field_validator("llama_parse_tier")
    @classmethod
    def _validate_tier_text(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        t = str(v).strip()
        if t not in LLAMA_PARSE_TIER_CHOICES:
            raise ValueError(
                f"llama_parse_tier must be one of {', '.join(sorted(LLAMA_PARSE_TIER_CHOICES))}; got {t!r}"
            )
        return t


class JobCreatedResponse(BaseModel):
    job_id: UUID


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    source_kind: str
    chunks_emitted: int
    error_message: str | None
    llama_parse_tier: str | None = Field(
        default=None,
        description="Per-job LlamaCloud tier if set at submit time; null means worker used env default only.",
    )
    created_at: str
    updated_at: str

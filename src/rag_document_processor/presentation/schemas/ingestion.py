from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

from rag_document_processor.core.config import LLAMA_PARSE_TIER_CHOICES
from rag_document_processor.core.ingest_embedding_options import (
    EMBEDDER_PROVIDER_CHOICES,
    EMBEDDING_PIPELINE_CHOICES,
    MACRO_SPLITTER_CHOICES,
)
from rag_document_processor.domain.entities.job import JobStatus, SourceKind


def _sorted_choices(choices: frozenset[str]) -> str:
    return ", ".join(sorted(choices))


_LLAMA_VALUES = _sorted_choices(LLAMA_PARSE_TIER_CHOICES)
_EMBED_PIPE_VALUES = _sorted_choices(EMBEDDING_PIPELINE_CHOICES)
_MACRO_VALUES = _sorted_choices(MACRO_SPLITTER_CHOICES)
_PROVIDER_VALUES = _sorted_choices(EMBEDDER_PROVIDER_CHOICES)

_EMBED_PIPE_DESC = (
    "Embedding strategy; omit to use EMBEDDING_PIPELINE from env. "
    f"Allowed values: {_EMBED_PIPE_VALUES}. "
    "late_chunking uses Jina only; chunk_then_embed can use OpenAI or Jina."
)
_MACRO_DESC = (
    "Macro document splitter; omit to use MACRO_SPLITTER from env. "
    f"Allowed values: {_MACRO_VALUES}."
)
_PROVIDER_DESC = (
    "Embedder for chunk_then_embed; omit to auto-pick when API keys are configured "
    "(OpenAI preferred when OPENAI_API_KEY is set). "
    f"Allowed values: {_PROVIDER_VALUES}. "
    "Ignored for late_chunking (always Jina)."
)
_EMBEDDING_MODEL_DESC = (
    "Override the embedding model id for whichever provider the job resolves to "
    "(OpenAI or Jina from pipeline + embedder_provider + keys). Omit to use OPENAI_EMBEDDING_MODEL or "
    "JINA_EMBEDDING_MODEL from env for the active side only."
)
_EMBEDDING_DIM_DESC = (
    "Output embedding vector size (Matryoshka / provider `dimensions`); omit to use EMBEDDING_DIMENSIONS from env. "
    "Allowed integers depend on the resolved embedding model; see GET /api/v1/embeddings/dimension-constraints. "
    "Request bodies accept 1-16384 here; the API returns 422 with active_embedder, embedding_model, "
    "requested_dimensions, and allowed_dimensions_min/max when the value does not match the model."
)

# Shared OpenAPI hints for multipart /file (keep in sync with JSON body fields above).
FORM_DESC_LLAMA_PARSE_TIER = (
    "LlamaCloud parse tier for PDF/DOCX; omit to use LLAMA_PARSE_TIER from env. "
    f"Allowed values: {_LLAMA_VALUES}."
)
FORM_DESC_EMBEDDING_DIMENSIONS = _EMBEDDING_DIM_DESC
FORM_DESC_EMBEDDING_PIPELINE = _EMBED_PIPE_DESC
FORM_DESC_MACRO_SPLITTER = _MACRO_DESC
FORM_DESC_EMBEDDER_PROVIDER = _PROVIDER_DESC
FORM_DESC_EMBEDDING_MODEL = _EMBEDDING_MODEL_DESC

_JOB_STATUS_VALUES = ", ".join(sorted(s.value for s in JobStatus))
_SOURCE_KIND_VALUES = ", ".join(sorted(s.value for s in SourceKind))


class UrlIngestRequest(BaseModel):
    url: HttpUrl = Field(description="HTTPS URL to fetch (e.g. PDF or DOCX).", examples=["https://example.com/doc.pdf"])
    llama_parse_tier: str | None = Field(
        default=None,
        description=(
            "LlamaCloud parse tier for PDF/DOCX from this URL; omit to use LLAMA_PARSE_TIER from env. "
            f"Allowed values: {_LLAMA_VALUES}."
        ),
        examples=["agentic"],
    )
    embedding_dimensions: int | None = Field(
        default=None,
        description=_EMBEDDING_DIM_DESC,
        ge=1,
        le=16384,
        examples=[1024],
    )
    embedding_pipeline: str | None = Field(
        default=None,
        max_length=32,
        description=_EMBED_PIPE_DESC,
        examples=["chunk_then_embed"],
    )
    macro_splitter: str | None = Field(
        default=None,
        max_length=32,
        description=_MACRO_DESC,
        examples=["recursive"],
    )
    embedder_provider: str | None = Field(
        default=None,
        max_length=16,
        description=_PROVIDER_DESC,
        examples=["openai"],
    )
    embedding_model: str | None = Field(
        default=None,
        max_length=128,
        description=_EMBEDDING_MODEL_DESC,
        examples=["jina-embeddings-v3"],
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
    texts: list[str] = Field(
        default_factory=list,
        min_length=1,
        description="One or more UTF-8 text segments to chunk and embed.",
        examples=[["First chunk of content.", "Second chunk of content."]],
    )
    llama_parse_tier: str | None = Field(
        default=None,
        description=(
            "Ignored for plain-text jobs (no LlamaCloud parse). If sent, must still be a valid tier. "
            f"Allowed values: {_LLAMA_VALUES}."
        ),
        examples=["agentic"],
    )
    embedding_dimensions: int | None = Field(
        default=None,
        description=_EMBEDDING_DIM_DESC,
        ge=1,
        le=16384,
        examples=[1024],
    )
    embedding_pipeline: str | None = Field(
        default=None,
        max_length=32,
        description=_EMBED_PIPE_DESC,
        examples=["chunk_then_embed"],
    )
    macro_splitter: str | None = Field(
        default=None,
        max_length=32,
        description=_MACRO_DESC,
        examples=["semantic"],
    )
    embedder_provider: str | None = Field(
        default=None,
        max_length=16,
        description=_PROVIDER_DESC,
        examples=["jina"],
    )
    embedding_model: str | None = Field(
        default=None,
        max_length=128,
        description=_EMBEDDING_MODEL_DESC,
        examples=["jina-embeddings-v3"],
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
    job_id: UUID = Field(description="Use this id with GET /jobs/{job_id} to poll status.")


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str = Field(description=f"Job lifecycle state. Values: {_JOB_STATUS_VALUES}.")
    source_kind: str = Field(description=f"How the job was submitted. Values: {_SOURCE_KIND_VALUES}.")
    chunks_emitted: int = Field(description="Number of vector chunks written after successful processing.")
    error_message: str | None = Field(
        default=None,
        description="Human-readable failure reason when status is failed; null otherwise.",
    )
    llama_parse_tier: str = Field(
        description=(
            "Effective LlamaCloud parse tier for this job (stored per-job value or LLAMA_PARSE_TIER from env). "
            f"Allowed values: {_LLAMA_VALUES}."
        ),
    )
    embedding_dimensions: int | None = Field(
        default=None,
        description=(
            "Effective embedding output size: stored per-job value or EMBEDDING_DIMENSIONS from env when omitted. "
            "Null only when neither is set. See GET /api/v1/embeddings/dimension-constraints."
        ),
    )
    embedding_pipeline: str = Field(
        description=(
            "Effective embedding pipeline for this job (stored override or EMBEDDING_PIPELINE from env). "
            f"Values: {_EMBED_PIPE_VALUES}."
        ),
    )
    macro_splitter: str = Field(
        description=(
            "Effective macro splitter (stored override or MACRO_SPLITTER from env). "
            f"Values: {_MACRO_VALUES}."
        ),
    )
    embedder_provider: str = Field(
        description=(
            "Active embedding API provider for this job: `openai` or `jina` (resolved from request + env + keys). "
            f"Request field `embedder_provider` (chunk_then_embed only) accepts: {_PROVIDER_VALUES}. "
            "late_chunking always resolves to jina."
        ),
    )
    embedding_model: str = Field(
        description="Effective embedding model id for the active provider (after overrides and env defaults).",
    )
    created_at: str = Field(description="ISO 8601 timestamp when the job was created.")
    updated_at: str = Field(description="ISO 8601 timestamp of the last status update.")

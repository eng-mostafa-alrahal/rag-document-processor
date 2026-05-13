"""Resolve and validate per-job embedding pipeline / provider / model overrides (multi-tenant)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from rag_document_processor.domain.exceptions import InvalidIngestEmbeddingOptionsError

if TYPE_CHECKING:
    from rag_document_processor.core.config import Settings

EMBEDDING_PIPELINE_CHOICES: frozenset[str] = frozenset(("late_chunking", "chunk_then_embed"))
MACRO_SPLITTER_CHOICES: frozenset[str] = frozenset(("semantic", "recursive", "token_aware"))
EMBEDDER_PROVIDER_CHOICES: frozenset[str] = frozenset(("openai", "jina"))

# OpenAPI / client generators often send type names as example values.
SCHEMA_PLACEHOLDER_MODEL_NAMES: frozenset[str] = frozenset(
    ("string", "integer", "int", "number", "float", "double", "boolean", "bool", "null", "object", "array")
)

EmbedderKind = Literal["openai", "jina"]
PipelineKind = Literal["late_chunking", "chunk_then_embed"]
MacroKind = Literal["semantic", "recursive", "token_aware"]


@dataclass(frozen=True, slots=True)
class ResolvedIngestEmbeddingOptions:
    embedding_pipeline: PipelineKind
    macro_splitter: MacroKind
    embedder: EmbedderKind
    openai_embedding_model: str
    jina_embedding_model: str


def _norm_opt_str(v: str | None) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def coerce_embedding_pipeline(raw: str | None) -> str | None:
    s = _norm_opt_str(raw)
    if s is None:
        return None
    sl = s.lower()
    if sl not in EMBEDDING_PIPELINE_CHOICES:
        allowed = ", ".join(sorted(EMBEDDING_PIPELINE_CHOICES))
        raise InvalidIngestEmbeddingOptionsError(f"embedding_pipeline must be one of: {allowed}. Got {s!r}.")
    return sl


def coerce_macro_splitter(raw: str | None) -> str | None:
    s = _norm_opt_str(raw)
    if s is None:
        return None
    sl = s.lower()
    if sl not in MACRO_SPLITTER_CHOICES:
        allowed = ", ".join(sorted(MACRO_SPLITTER_CHOICES))
        raise InvalidIngestEmbeddingOptionsError(f"macro_splitter must be one of: {allowed}. Got {s!r}.")
    return sl


def coerce_embedder_provider(raw: str | None) -> str | None:
    s = _norm_opt_str(raw)
    if s is None:
        return None
    sl = s.lower()
    if sl not in EMBEDDER_PROVIDER_CHOICES:
        allowed = ", ".join(sorted(EMBEDDER_PROVIDER_CHOICES))
        raise InvalidIngestEmbeddingOptionsError(f"embedder_provider must be one of: {allowed}. Got {s!r}.")
    return sl


def coerce_embedding_model(raw: str | None, *, field: str, max_len: int = 128) -> str | None:
    s = _norm_opt_str(raw)
    if s is None:
        return None
    if len(s) > max_len:
        raise InvalidIngestEmbeddingOptionsError(f"{field} must be at most {max_len} characters.")
    if s.lower() in SCHEMA_PLACEHOLDER_MODEL_NAMES:
        raise InvalidIngestEmbeddingOptionsError(
            f"{field} must be a real provider model id, not a schema placeholder ({s!r}). "
            "Omit the field to use OPENAI_EMBEDDING_MODEL or JINA_EMBEDDING_MODEL from the server configuration."
        )
    return s


def resolve_ingest_embedding_options(
    settings: Settings,
    *,
    job_embedding_pipeline: str | None,
    job_macro_splitter: str | None,
    job_embedder_provider: str | None,
    job_openai_embedding_model: str | None,
    job_jina_embedding_model: str | None,
) -> ResolvedIngestEmbeddingOptions:
    pipeline_raw = job_embedding_pipeline or settings.embedding_pipeline
    if pipeline_raw not in EMBEDDING_PIPELINE_CHOICES:
        allowed = ", ".join(sorted(EMBEDDING_PIPELINE_CHOICES))
        raise InvalidIngestEmbeddingOptionsError(f"embedding_pipeline must be one of: {allowed}.")
    pipeline: PipelineKind = pipeline_raw  # type: ignore[assignment]

    macro_raw = job_macro_splitter or settings.macro_splitter
    if macro_raw not in MACRO_SPLITTER_CHOICES:
        allowed = ", ".join(sorted(MACRO_SPLITTER_CHOICES))
        raise InvalidIngestEmbeddingOptionsError(f"macro_splitter must be one of: {allowed}.")
    macro: MacroKind = macro_raw  # type: ignore[assignment]

    openai_model = (job_openai_embedding_model or settings.openai_embedding_model or "").strip()
    jina_model = (job_jina_embedding_model or settings.jina_embedding_model or "").strip()
    if not openai_model:
        raise InvalidIngestEmbeddingOptionsError("Resolved OpenAI embedding model name is empty.")
    if not jina_model:
        raise InvalidIngestEmbeddingOptionsError("Resolved Jina embedding model name is empty.")

    if pipeline == "late_chunking":
        if job_embedder_provider == "openai":
            raise InvalidIngestEmbeddingOptionsError(
                "embedder_provider cannot be openai when embedding_pipeline is late_chunking (requires Jina)."
            )
        if not settings.jina_api_key:
            raise InvalidIngestEmbeddingOptionsError(
                "JINA_API_KEY is required for late_chunking jobs. Configure the server key or choose chunk_then_embed."
            )
        return ResolvedIngestEmbeddingOptions(
            embedding_pipeline=pipeline,
            macro_splitter=macro,
            embedder="jina",
            openai_embedding_model=openai_model,
            jina_embedding_model=jina_model,
        )

    # chunk_then_embed
    prov = job_embedder_provider
    if prov == "openai":
        if not settings.openai_api_key:
            raise InvalidIngestEmbeddingOptionsError(
                "embedder_provider is openai but OPENAI_API_KEY is not configured on this deployment."
            )
        embedder: EmbedderKind = "openai"
    elif prov == "jina":
        if not settings.jina_api_key:
            raise InvalidIngestEmbeddingOptionsError(
                "embedder_provider is jina but JINA_API_KEY is not configured on this deployment."
            )
        embedder = "jina"
    else:
        if settings.openai_api_key:
            embedder = "openai"
        elif settings.jina_api_key:
            embedder = "jina"
        else:
            raise InvalidIngestEmbeddingOptionsError(
                "OPENAI_API_KEY or JINA_API_KEY is required for chunk_then_embed. "
                "Set a key or pass embedder_provider with a matching configured provider."
            )

    return ResolvedIngestEmbeddingOptions(
        embedding_pipeline=pipeline,
        macro_splitter=macro,
        embedder=embedder,
        openai_embedding_model=openai_model,
        jina_embedding_model=jina_model,
    )

"""Validate optional embedding output size against the active embedder model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from rag_document_processor.core.ingest_embedding_options import SCHEMA_PLACEHOLDER_MODEL_NAMES
from rag_document_processor.domain.exceptions import InvalidEmbeddingDimensionsError


@dataclass(frozen=True, slots=True)
class EmbeddingDimensionRule:
    """Single policy row: first matching rule wins for that provider."""

    provider: Literal["openai", "jina"]
    label: str
    match_description: str
    model_id_substrings_any: tuple[str, ...]
    model_example_ids: tuple[str, ...]
    min_dim: int
    max_dim: int
    recommended_dims: tuple[int, ...] | None
    notes: str
    extra_match: Callable[[str], bool] | None = None

    def matches(self, model_id: str) -> bool:
        ml = model_id.strip().lower()
        if any(s in ml for s in self.model_id_substrings_any):
            return True
        if self.extra_match is not None and self.extra_match(ml):
            return True
        return False


# OpenAI: https://platform.openai.com/docs/guides/embeddings
_OPENAI_3_SMALL = EmbeddingDimensionRule(
    provider="openai",
    label="OpenAI text-embedding-3-small",
    match_description="Model id contains `embedding-3-small`, or ends with `3-small` (short ids).",
    model_id_substrings_any=("embedding-3-small",),
    model_example_ids=("text-embedding-3-small",),
    min_dim=256,
    max_dim=1536,
    recommended_dims=None,
    notes="Matryoshka sizes supported by OpenAI for this model; bounds are inclusive.",
    extra_match=lambda ml: ml.endswith("3-small"),
)
_OPENAI_3_LARGE = EmbeddingDimensionRule(
    provider="openai",
    label="OpenAI text-embedding-3-large",
    match_description="Model id contains `embedding-3-large`, or ends with `3-large` (short ids).",
    model_id_substrings_any=("embedding-3-large",),
    model_example_ids=("text-embedding-3-large",),
    min_dim=256,
    max_dim=3072,
    recommended_dims=None,
    notes="Matryoshka sizes supported by OpenAI for this model; bounds are inclusive.",
    extra_match=lambda ml: ml.endswith("3-large"),
)

OPENAI_EMBEDDING_DIMENSION_RULES: tuple[EmbeddingDimensionRule, ...] = (
    _OPENAI_3_SMALL,
    _OPENAI_3_LARGE,
)

# Jina v3 MRL: product docs cite truncation down to 32 dims; model card max output length 1024.
# https://jina.ai/embeddings/ — v3 “down to 32”; v4 “down to 128”.
# Jina public API examples use dimensions 1–1024 for some batch paths; we stay conservative per family.
_JINA_V5_NANO = EmbeddingDimensionRule(
    provider="jina",
    label="Jina embeddings v5 (text/omni nano)",
    match_description="Model id contains `jina-embeddings-v5-text-nano` or `jina-embeddings-v5-omni-nano`.",
    model_id_substrings_any=("jina-embeddings-v5-text-nano", "jina-embeddings-v5-omni-nano"),
    model_example_ids=("jina-embeddings-v5-text-nano", "jina-ai/jina-embeddings-v5-text-nano"),
    min_dim=1,
    max_dim=768,
    recommended_dims=(256, 512, 768),
    notes="Nano v5 models are documented with 768-d default output; treat 1–768 as the adjustable range.",
    extra_match=None,
)
_JINA_V5_SMALL = EmbeddingDimensionRule(
    provider="jina",
    label="Jina embeddings v5 (text/omni small)",
    match_description="Model id contains `jina-embeddings-v5-text-small` or `jina-embeddings-v5-omni-small`.",
    model_id_substrings_any=("jina-embeddings-v5-text-small", "jina-embeddings-v5-omni-small"),
    model_example_ids=("jina-embeddings-v5-text-small", "jina-ai/jina-embeddings-v5-text-small"),
    min_dim=1,
    max_dim=1024,
    recommended_dims=(256, 512, 768, 1024),
    notes="Jina batch API documents output dimensions 1–1024 for compatible models; inclusive integers.",
    extra_match=None,
)
_JINA_V3 = EmbeddingDimensionRule(
    provider="jina",
    label="Jina embeddings v3 (Matryoshka)",
    match_description="Model id contains `jina-embeddings-v3` (covers `jina-ai/jina-embeddings-v3`, etc.).",
    model_id_substrings_any=("jina-embeddings-v3",),
    model_example_ids=("jina-embeddings-v3", "jina-ai/jina-embeddings-v3"),
    min_dim=32,
    max_dim=1024,
    recommended_dims=(32, 64, 128, 256, 512, 768, 1024),
    notes=(
        "Matryoshka (MRL): Jina documents dimension truncation for v3 down to 32 with max 1024; "
        "any inclusive integer in this range is accepted here. See https://jina.ai/embeddings/ and model card."
    ),
    extra_match=None,
)
_JINA_V4 = EmbeddingDimensionRule(
    provider="jina",
    label="Jina embeddings v4 (Matryoshka)",
    match_description="Model id contains `jina-embeddings-v4`.",
    model_id_substrings_any=("jina-embeddings-v4",),
    model_example_ids=("jina-embeddings-v4",),
    min_dim=128,
    max_dim=1024,
    recommended_dims=None,
    notes="Jina documents v4 MRL with a higher floor than v3 (128 minimum in product messaging).",
    extra_match=None,
)
_JINA_V2 = EmbeddingDimensionRule(
    provider="jina",
    label="Jina embeddings v2 family",
    match_description="Model id contains `jina-embeddings-v2`.",
    model_id_substrings_any=("jina-embeddings-v2",),
    model_example_ids=("jina-embeddings-v2-base-en",),
    min_dim=256,
    max_dim=1024,
    recommended_dims=None,
    notes="Conservative Matryoshka range for v2-style `jina-embeddings-v2-*` ids used with the Jina API.",
    extra_match=None,
)
_JINA_EMBEDDINGS_FALLBACK = EmbeddingDimensionRule(
    provider="jina",
    label="Other Jina `jina-embeddings-*` models",
    match_description="Model id contains `jina-embeddings` (after more specific rules did not match).",
    model_id_substrings_any=("jina-embeddings",),
    model_example_ids=("jina-embeddings-v6",),
    min_dim=256,
    max_dim=1024,
    recommended_dims=None,
    notes="Fallback for newer `jina-embeddings-*` ids until pinned to a specific rule; prefer explicit model ids.",
    extra_match=None,
)

JINA_EMBEDDING_DIMENSION_RULES: tuple[EmbeddingDimensionRule, ...] = (
    _JINA_V5_NANO,
    _JINA_V5_SMALL,
    _JINA_V3,
    _JINA_V4,
    _JINA_V2,
    _JINA_EMBEDDINGS_FALLBACK,
)


def public_embedding_dimension_rules() -> tuple[EmbeddingDimensionRule, ...]:
    """All documented rules (OpenAI first, then Jina in evaluation order)."""
    return OPENAI_EMBEDDING_DIMENSION_RULES + JINA_EMBEDDING_DIMENSION_RULES


def _match_openai_rule(model: str) -> EmbeddingDimensionRule | None:
    for rule in OPENAI_EMBEDDING_DIMENSION_RULES:
        if rule.matches(model):
            return rule
    return None


def _match_jina_rule(model: str) -> EmbeddingDimensionRule | None:
    for rule in JINA_EMBEDDING_DIMENSION_RULES:
        if rule.matches(model):
            return rule
    return None


def _unsupported_matryoshka_hint(embedder: Literal["openai", "jina"]) -> str:
    if embedder == "openai":
        return (
            "Only text-embedding-3-small (256-1536) and text-embedding-3-large (256-3072) accept custom sizes; "
            "bounds are inclusive. For other OpenAI models, omit embedding_dimensions. "
            "See GET /api/v1/embeddings/dimension-constraints for the full table (under your deployment API_PREFIX)."
        )
    return (
        "Custom output sizes depend on the Jina model id (for example jina-embeddings-v3 allows 32-1024). "
        "For models without a matching rule, omit embedding_dimensions. "
        "See GET /api/v1/embeddings/dimension-constraints for the full table (under your deployment API_PREFIX)."
    )


def matryoshka_dimension_range(
    *,
    embedder: Literal["openai", "jina"],
    openai_embedding_model: str,
    jina_embedding_model: str,
) -> tuple[int, int] | None:
    """Inclusive (min, max) for models that support a `dimensions` parameter; None if not supported."""
    if embedder == "openai":
        r = _match_openai_rule(openai_embedding_model)
    else:
        r = _match_jina_rule(jina_embedding_model)
    if r is None:
        return None
    return (r.min_dim, r.max_dim)


def _dimension_mismatch_base(
    *,
    embedder: Literal["openai", "jina"],
    openai_embedding_model: str,
    jina_embedding_model: str,
    dim: int,
) -> dict[str, object]:
    model = (openai_embedding_model if embedder == "openai" else jina_embedding_model).strip()
    return {
        "active_embedder": embedder,
        "embedding_model": model,
        "requested_dimensions": dim,
    }


def validate_embedding_dimensions(
    *,
    embedder: Literal["openai", "jina"],
    openai_embedding_model: str,
    jina_embedding_model: str,
    dim: int | None,
) -> None:
    if dim is None:
        return
    model = (openai_embedding_model if embedder == "openai" else jina_embedding_model).strip()
    base = _dimension_mismatch_base(
        embedder=embedder,
        openai_embedding_model=openai_embedding_model,
        jina_embedding_model=jina_embedding_model,
        dim=dim,
    )
    r = matryoshka_dimension_range(
        embedder=embedder,
        openai_embedding_model=openai_embedding_model,
        jina_embedding_model=jina_embedding_model,
    )
    if r is None:
        if model.lower() in SCHEMA_PLACEHOLDER_MODEL_NAMES:
            raise InvalidEmbeddingDimensionsError(
                f"embedding_dimensions={dim} was set, but the active {embedder} model id {model!r} is not a real "
                "provider model (often an OpenAPI placeholder). Set `embedding_model` to a real provider model id, "
                "or omit embedding_dimensions.",
                payload={
                    **base,
                    "reason": "placeholder_model_id",
                    "allowed_dimensions_min": None,
                    "allowed_dimensions_max": None,
                },
            )
        raise InvalidEmbeddingDimensionsError(
            f"embedding_dimensions={dim} is not supported for the active {embedder} model {model!r} "
            f"(this model does not accept a custom output size here). {_unsupported_matryoshka_hint(embedder)}",
            payload={
                **base,
                "reason": "model_does_not_support_custom_dimensions",
                "allowed_dimensions_min": None,
                "allowed_dimensions_max": None,
            },
        )
    lo, hi = r
    if dim < lo or dim > hi:
        raise InvalidEmbeddingDimensionsError(
            f"embedding_dimensions={dim} does not match the active {embedder} model {model!r}: "
            f"use an integer from {lo} to {hi} inclusive (you can list rules at GET /api/v1/embeddings/dimension-constraints).",
            payload={
                **base,
                "reason": "out_of_range",
                "allowed_dimensions_min": lo,
                "allowed_dimensions_max": hi,
            },
        )


def coalesce_embedding_dimensions(job_value: int | None, env_default: int | None) -> int | None:
    return job_value if job_value is not None else env_default

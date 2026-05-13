from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EmbeddingDimensionRuleItem(BaseModel):
    """One row of the server’s embedding-dimension policy (Matryoshka / `dimensions` API)."""

    provider: Literal["openai", "jina"] = Field(description="Which API receives the `dimensions` parameter.")
    label: str = Field(description="Short human-readable name for this rule.")
    match: str = Field(
        description="How a request model id is matched: case-insensitive substring against any listed token.",
    )
    model_id_substrings_any: list[str] = Field(
        description="If the active model id contains any of these substrings (case-insensitive), this rule applies.",
    )
    model_example_ids: list[str] = Field(
        default_factory=list,
        description="Example model ids that fall under this rule (not exhaustive).",
    )
    min_dimensions: int = Field(ge=1, description="Minimum inclusive `embedding_dimensions` for this rule.")
    max_dimensions: int = Field(ge=1, description="Maximum inclusive `embedding_dimensions` for this rule.")
    recommended_dimensions: list[int] | None = Field(
        default=None,
        description="Optional benchmark sizes from provider docs; any integer in [min_dimensions, max_dimensions] is still accepted unless the API says otherwise.",
    )
    notes: str = Field(description="Provider-specific caveats and links to rationale.")


class EmbeddingDimensionConstraintsResponse(BaseModel):
    rules: list[EmbeddingDimensionRuleItem] = Field(
        description="Ordered most-specific-first; the first matching rule wins for a given model id.",
    )

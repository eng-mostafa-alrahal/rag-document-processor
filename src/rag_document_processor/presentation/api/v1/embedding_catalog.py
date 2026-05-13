from __future__ import annotations

from fastapi import APIRouter

from rag_document_processor.core.embedding_dimensions import public_embedding_dimension_rules
from rag_document_processor.presentation.schemas.embedding_catalog import (
    EmbeddingDimensionConstraintsResponse,
    EmbeddingDimensionRuleItem,
)

router = APIRouter(tags=["embeddings"])


@router.get(
    "/embeddings/dimension-constraints",
    response_model=EmbeddingDimensionConstraintsResponse,
    summary="List embedding output size rules by model",
)
async def list_embedding_dimension_constraints() -> EmbeddingDimensionConstraintsResponse:
    """Return which `embedding_dimensions` values are accepted for known OpenAI and Jina model ids.

    Rules are evaluated in order; the first rule whose `model_id_substrings_any` matches the active model id wins.
    """
    rules = [
        EmbeddingDimensionRuleItem(
            provider=r.provider,
            label=r.label,
            match=r.match_description,
            model_id_substrings_any=list(r.model_id_substrings_any),
            model_example_ids=list(r.model_example_ids),
            min_dimensions=r.min_dim,
            max_dimensions=r.max_dim,
            recommended_dimensions=list(r.recommended_dims) if r.recommended_dims else None,
            notes=r.notes,
        )
        for r in public_embedding_dimension_rules()
    ]
    return EmbeddingDimensionConstraintsResponse(rules=rules)

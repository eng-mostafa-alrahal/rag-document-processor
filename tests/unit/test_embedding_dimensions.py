from __future__ import annotations

import pytest

from rag_document_processor.core.embedding_dimensions import (
    matryoshka_dimension_range,
    public_embedding_dimension_rules,
    validate_embedding_dimensions,
)
from rag_document_processor.domain.exceptions import InvalidEmbeddingDimensionsError


def test_jina_v3_range_32_to_1024() -> None:
    assert matryoshka_dimension_range(
        embedder="jina",
        openai_embedding_model="text-embedding-3-small",
        jina_embedding_model="jina-embeddings-v3",
    ) == (32, 1024)
    validate_embedding_dimensions(
        embedder="jina",
        openai_embedding_model="x",
        jina_embedding_model="jina-ai/jina-embeddings-v3",
        dim=32,
    )
    validate_embedding_dimensions(
        embedder="jina",
        openai_embedding_model="x",
        jina_embedding_model="jina-embeddings-v3",
        dim=1024,
    )
    with pytest.raises(InvalidEmbeddingDimensionsError) as err:
        validate_embedding_dimensions(
            embedder="jina",
            openai_embedding_model="x",
            jina_embedding_model="jina-embeddings-v3",
            dim=31,
        )
    assert err.value.payload["reason"] == "out_of_range"
    assert err.value.payload["allowed_dimensions_min"] == 32
    assert err.value.payload["allowed_dimensions_max"] == 1024
    assert err.value.payload["active_embedder"] == "jina"
    assert err.value.payload["embedding_model"] == "jina-embeddings-v3"
    assert err.value.payload["requested_dimensions"] == 31
    with pytest.raises(InvalidEmbeddingDimensionsError):
        validate_embedding_dimensions(
            embedder="jina",
            openai_embedding_model="x",
            jina_embedding_model="jina-embeddings-v3",
            dim=1025,
        )


def test_jina_v4_floor_128() -> None:
    validate_embedding_dimensions(
        embedder="jina",
        openai_embedding_model="x",
        jina_embedding_model="jina-embeddings-v4",
        dim=128,
    )
    with pytest.raises(InvalidEmbeddingDimensionsError):
        validate_embedding_dimensions(
            embedder="jina",
            openai_embedding_model="x",
            jina_embedding_model="jina-embeddings-v4",
            dim=127,
        )


def test_jina_v2_uses_conservative_range() -> None:
    r = matryoshka_dimension_range(
        embedder="jina",
        openai_embedding_model="x",
        jina_embedding_model="jina-embeddings-v2-base-en",
    )
    assert r == (256, 1024)


def test_openai_3_small_range() -> None:
    assert matryoshka_dimension_range(
        embedder="openai",
        openai_embedding_model="text-embedding-3-small",
        jina_embedding_model="jina-embeddings-v3",
    ) == (256, 1536)
    with pytest.raises(InvalidEmbeddingDimensionsError):
        validate_embedding_dimensions(
            embedder="openai",
            openai_embedding_model="text-embedding-3-small",
            jina_embedding_model="x",
            dim=255,
        )


def test_public_rules_include_v3_recommended_dims() -> None:
    rules = public_embedding_dimension_rules()
    v3 = next(r for r in rules if r.label == "Jina embeddings v3 (Matryoshka)")
    assert v3.min_dim == 32 and v3.max_dim == 1024
    assert v3.recommended_dims is not None and 32 in v3.recommended_dims and 1024 in v3.recommended_dims

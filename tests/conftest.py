from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _default_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from rag_document_processor.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get("DATABASE_URL", "postgresql+asyncpg://rag:rag@localhost:5432/rag"),
    )
    monkeypatch.setenv("JWT_SECRET", os.environ.get("JWT_SECRET", "unit-test-access-secret-32chars__"))
    monkeypatch.setenv(
        "JWT_REFRESH_SECRET",
        os.environ.get("JWT_REFRESH_SECRET", "unit-test-refresh-secret-32chars_"),
    )
    monkeypatch.setenv("EMBEDDING_PIPELINE", os.environ.get("EMBEDDING_PIPELINE", "chunk_then_embed"))
    monkeypatch.setenv("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "sk-test-unit"))
    monkeypatch.setenv("STORAGE_BACKEND", os.environ.get("STORAGE_BACKEND", "local"))
    monkeypatch.setenv("LOCAL_STORAGE_PATH", os.environ.get("LOCAL_STORAGE_PATH", "./data/test_uploads"))
    yield
    get_settings.cache_clear()

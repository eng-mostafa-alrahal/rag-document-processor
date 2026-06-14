"""Mint an API key directly against the database (bootstrap / admin tool).

Usage (from repo root):

    uv run python scripts/create_api_key.py "My client name"

Prints the full secret key once. Store it securely; only its hash is persisted.
The same can be done over HTTP via `POST /api/v1/api-keys` with the
`X-Admin-Secret` header.
"""

from __future__ import annotations

import asyncio
import sys

from rag_document_processor.application.use_cases.api_keys.manage import CreateApiKeyUseCase
from rag_document_processor.core.config import get_settings
from rag_document_processor.infrastructure.db.session import create_engine, create_session_factory


async def _main(name: str) -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        uc = CreateApiKeyUseCase(session_factory)
        dto = await uc.execute(name=name)
    finally:
        await engine.dispose()

    print("API key created.")
    print(f"  id:         {dto.id}")
    print(f"  name:       {dto.name}")
    print(f"  prefix:     {dto.key_prefix}")
    print(f"  created_at: {dto.created_at}")
    print()
    print("Secret (shown once \u2014 store it now):")
    print(f"  {dto.api_key}")
    return 0


if __name__ == "__main__":
    key_name = " ".join(sys.argv[1:]).strip() or "default"
    raise SystemExit(asyncio.run(_main(key_name)))

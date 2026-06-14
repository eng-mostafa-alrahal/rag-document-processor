from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_document_processor.application.dtos import ApiKeyCreatedDTO, ApiKeyDTO
from rag_document_processor.application.ports.repositories import IApiKeyRepository
from rag_document_processor.domain.entities.api_key import ApiKey
from rag_document_processor.domain.exceptions import ApiKeyNotFoundError
from rag_document_processor.infrastructure.db.repositories.api_key_repo import SqlApiKeyRepository
from rag_document_processor.infrastructure.security.api_key_hashing import generate_api_key


def _to_dto(key: ApiKey) -> ApiKeyDTO:
    return ApiKeyDTO(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        is_active=key.is_active,
        created_at=key.created_at.isoformat(),
        last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
    )


class CreateApiKeyUseCase:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def execute(self, *, name: str) -> ApiKeyCreatedDTO:
        generated = generate_api_key()
        key_id = uuid4()
        async with self._session_factory() as session:
            keys: IApiKeyRepository = SqlApiKeyRepository(session)
            created = await keys.create(
                key_id=key_id,
                name=name.strip() or "unnamed",
                key_prefix=generated.key_prefix,
                key_hash=generated.key_hash,
            )
            await session.commit()
        return ApiKeyCreatedDTO(
            id=created.id,
            name=created.name,
            key_prefix=created.key_prefix,
            api_key=generated.raw_key,
            created_at=created.created_at.isoformat(),
        )


class ListApiKeysUseCase:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def execute(self) -> list[ApiKeyDTO]:
        async with self._session_factory() as session:
            keys: IApiKeyRepository = SqlApiKeyRepository(session)
            rows = await keys.list_all()
        return [_to_dto(k) for k in rows]


class RevokeApiKeyUseCase:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def execute(self, *, key_id: UUID) -> None:
        async with self._session_factory() as session:
            keys: IApiKeyRepository = SqlApiKeyRepository(session)
            revoked = await keys.revoke(key_id)
            if not revoked:
                raise ApiKeyNotFoundError()
            await session.commit()

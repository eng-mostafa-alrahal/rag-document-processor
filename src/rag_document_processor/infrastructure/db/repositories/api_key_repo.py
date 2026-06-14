from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rag_document_processor.domain.entities.api_key import ApiKey
from rag_document_processor.infrastructure.db.models import ApiKeyModel


def _entity_from_row(row: ApiKeyModel) -> ApiKey:
    return ApiKey(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        is_active=row.is_active,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
    )


class SqlApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, key_id: UUID, name: str, key_prefix: str, key_hash: str) -> ApiKey:
        row = ApiKeyModel(
            id=key_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            is_active=True,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _entity_from_row(row)

    async def get_active_by_hash(self, key_hash: str) -> ApiKey | None:
        res = await self._session.execute(
            select(ApiKeyModel).where(
                ApiKeyModel.key_hash == key_hash,
                ApiKeyModel.is_active.is_(True),
            )
        )
        row = res.scalar_one_or_none()
        return _entity_from_row(row) if row else None

    async def list_all(self) -> list[ApiKey]:
        res = await self._session.execute(select(ApiKeyModel).order_by(ApiKeyModel.created_at.desc()))
        return [_entity_from_row(row) for row in res.scalars().all()]

    async def revoke(self, key_id: UUID) -> bool:
        res = await self._session.execute(
            update(ApiKeyModel)
            .where(ApiKeyModel.id == key_id, ApiKeyModel.is_active.is_(True))
            .values(is_active=False)
        )
        return (res.rowcount or 0) > 0

    async def touch_last_used(self, key_id: UUID) -> None:
        await self._session.execute(
            update(ApiKeyModel).where(ApiKeyModel.id == key_id).values(last_used_at=datetime.now(tz=UTC))
        )

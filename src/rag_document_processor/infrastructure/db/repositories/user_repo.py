from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_document_processor.domain.entities.user import User
from rag_document_processor.infrastructure.db.models import UserModel


def _user_from_row(row: UserModel) -> User:
    return User(
        id=row.id,
        email=row.email,
        hashed_password=row.hashed_password,
        is_active=row.is_active,
        created_at=row.created_at,
    )


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user: User) -> User:
        row = UserModel(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            is_active=user.is_active,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _user_from_row(row)

    async def get_by_email(self, email: str) -> User | None:
        res = await self._session.execute(select(UserModel).where(UserModel.email == email))
        row = res.scalar_one_or_none()
        return _user_from_row(row) if row else None

    async def get_by_id(self, user_id: UUID) -> User | None:
        res = await self._session.execute(select(UserModel).where(UserModel.id == user_id))
        row = res.scalar_one_or_none()
        return _user_from_row(row) if row else None

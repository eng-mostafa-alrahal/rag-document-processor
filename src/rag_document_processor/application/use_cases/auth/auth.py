from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_document_processor.application.dtos import TokenPairDTO, UserPublicDTO
from rag_document_processor.application.ports.password_hasher import IPasswordHasher
from rag_document_processor.application.ports.repositories import IUserRepository
from rag_document_processor.application.ports.token_service import IRefreshTokenStore, ITokenService
from rag_document_processor.domain.entities.user import User
from rag_document_processor.domain.exceptions import InvalidCredentialsError, UserAlreadyExistsError, UserInactiveError
from rag_document_processor.infrastructure.db.repositories.user_repo import SqlUserRepository


class RegisterUserUseCase:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        password_hasher: IPasswordHasher,
    ) -> None:
        self._session_factory = session_factory
        self._password_hasher = password_hasher

    async def execute(self, *, email: str, password: str) -> UserPublicDTO:
        email_norm = email.strip().lower()
        async with self._session_factory() as session:
            users: IUserRepository = SqlUserRepository(session)
            if await users.get_by_email(email_norm):
                raise UserAlreadyExistsError()
            user = User(
                id=uuid4(),
                email=email_norm,
                hashed_password=self._password_hasher.hash(password),
                is_active=True,
                created_at=None,
            )
            created = await users.create(user)
            await session.commit()
        return UserPublicDTO(id=created.id, email=created.email)


class LoginUseCase:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        password_hasher: IPasswordHasher,
        tokens: ITokenService,
    ) -> None:
        self._session_factory = session_factory
        self._password_hasher = password_hasher
        self._tokens = tokens

    async def execute(self, *, email: str, password: str) -> TokenPairDTO:
        email_norm = email.strip().lower()
        async with self._session_factory() as session:
            users: IUserRepository = SqlUserRepository(session)
            user = await users.get_by_email(email_norm)
            if user is None or not self._password_hasher.verify(password, user.hashed_password):
                raise InvalidCredentialsError()
            if not user.is_active:
                raise UserInactiveError()
        access = self._tokens.create_access_token(user_id=user.id, email=user.email)
        refresh = self._tokens.create_refresh_token(user_id=user.id, jti=str(uuid4()))
        return TokenPairDTO(access_token=access, refresh_token=refresh)


class RefreshTokenUseCase:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tokens: ITokenService,
        refresh_store: IRefreshTokenStore,
    ) -> None:
        self._session_factory = session_factory
        self._tokens = tokens
        self._refresh_store = refresh_store

    async def execute(self, *, refresh_token: str) -> TokenPairDTO:
        try:
            payload = self._tokens.decode_refresh(refresh_token)
        except Exception as e:
            raise InvalidCredentialsError() from e
        if payload.get("type") != "refresh":
            raise InvalidCredentialsError()
        jti = payload.get("jti")
        if not jti or await self._refresh_store.is_revoked(str(jti)):
            raise InvalidCredentialsError()
        from uuid import UUID as UUIDType

        user_id = UUIDType(str(payload["sub"]))
        async with self._session_factory() as session:
            users: IUserRepository = SqlUserRepository(session)
            user = await users.get_by_id(user_id)
            if user is None or not user.is_active:
                raise InvalidCredentialsError()
        access = self._tokens.create_access_token(user_id=user.id, email=user.email)
        new_refresh = self._tokens.create_refresh_token(user_id=user.id, jti=str(uuid4()))
        # rotate: revoke old jti until its natural expiry
        exp = payload.get("exp")
        ttl = 60 * 60 * 24 * 7
        if isinstance(exp, (int, float)):
            import time

            ttl = max(int(exp - time.time()), 60)
        await self._refresh_store.revoke(str(jti), ttl_seconds=ttl)
        return TokenPairDTO(access_token=access, refresh_token=new_refresh)


class LogoutUseCase:
    def __init__(self, tokens: ITokenService, refresh_store: IRefreshTokenStore) -> None:
        self._tokens = tokens
        self._refresh_store = refresh_store

    async def execute(self, *, refresh_token: str) -> None:
        try:
            payload = self._tokens.decode_refresh(refresh_token)
        except Exception:
            return
        jti = payload.get("jti")
        if not jti:
            return
        exp = payload.get("exp")
        ttl = 60 * 60 * 24 * 7
        if isinstance(exp, (int, float)):
            import time

            ttl = max(int(exp - time.time()), 60)
        await self._refresh_store.revoke(str(jti), ttl_seconds=ttl)

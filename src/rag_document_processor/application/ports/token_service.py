from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ITokenService(Protocol):
    def create_access_token(self, *, user_id: UUID, email: str) -> str: ...

    def create_refresh_token(self, *, user_id: UUID, jti: str) -> str: ...

    def decode_access(self, token: str) -> dict: ...

    def decode_refresh(self, token: str) -> dict: ...


class IRefreshTokenStore(Protocol):
    """Redis-backed jti revocation for refresh tokens."""

    async def revoke(self, jti: str, ttl_seconds: int) -> None: ...

    async def is_revoked(self, jti: str) -> bool: ...

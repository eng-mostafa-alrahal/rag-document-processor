from __future__ import annotations

import redis.asyncio as redis

from rag_document_processor.application.ports.token_service import IRefreshTokenStore


class RedisRefreshTokenStore:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        await self._r.setex(f"refresh:revoked:{jti}", ttl_seconds, "1")

    async def is_revoked(self, jti: str) -> bool:
        return bool(await self._r.exists(f"refresh:revoked:{jti}"))

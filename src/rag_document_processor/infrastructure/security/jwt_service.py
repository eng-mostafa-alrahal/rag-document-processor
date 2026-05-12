from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt

from rag_document_processor.core.config import Settings


class JwtTokenService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_access_token(self, *, user_id: UUID, email: str) -> str:
        now = datetime.now(tz=UTC)
        payload = {
            "sub": str(user_id),
            "email": email,
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": now + timedelta(minutes=self._settings.jwt_access_expire_minutes),
        }
        return jwt.encode(payload, self._settings.jwt_secret, algorithm="HS256")

    def create_refresh_token(self, *, user_id: UUID, jti: str) -> str:
        now = datetime.now(tz=UTC)
        payload = {
            "sub": str(user_id),
            "jti": jti,
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": now + timedelta(days=self._settings.jwt_refresh_expire_days),
        }
        return jwt.encode(payload, self._settings.jwt_refresh_secret, algorithm="HS256")

    def decode_access(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, self._settings.jwt_secret, algorithms=["HS256"])

    def decode_refresh(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, self._settings.jwt_refresh_secret, algorithms=["HS256"])

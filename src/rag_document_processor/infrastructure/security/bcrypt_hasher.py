from __future__ import annotations

from passlib.context import CryptContext


class BcryptPasswordHasher:
    def __init__(self) -> None:
        self._ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash(self, password: str) -> str:
        return self._ctx.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        return self._ctx.verify(password, hashed)

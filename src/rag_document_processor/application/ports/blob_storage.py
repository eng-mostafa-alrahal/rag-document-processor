from __future__ import annotations

from typing import BinaryIO, Protocol


class IBlobStorage(Protocol):
    async def put(self, key: str, data: bytes, *, content_type: str) -> str:
        """Store bytes; returns storage key."""

    async def get_bytes(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

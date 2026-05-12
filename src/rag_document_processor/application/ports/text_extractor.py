from __future__ import annotations

from typing import Protocol


class ITextExtractor(Protocol):
    async def extract(self, data: bytes, *, content_type: str | None, filename: str | None) -> str: ...

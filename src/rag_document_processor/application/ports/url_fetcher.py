from __future__ import annotations

from typing import Protocol


class IUrlFetcher(Protocol):
    async def fetch(self, url: str) -> tuple[bytes, str | None]:
        """Return (body_bytes, content_type)."""

from __future__ import annotations

from pathlib import Path

import aiofiles

from rag_document_processor.application.ports.blob_storage import IBlobStorage


class LocalBlobStorage(IBlobStorage):
    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("..", "").lstrip("/\\")
        return self._base / safe

    async def put(self, key: str, data: bytes, *, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return key

    async def get_bytes(self, key: str) -> bytes:
        path = self._path(key)
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

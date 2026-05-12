from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import redis.asyncio as redis

from rag_document_processor.application.ports.embedding_sink import IEmbeddingSink
from rag_document_processor.domain.value_objects.embedded_chunk import EmbeddedChunk


class RedisStreamSink(IEmbeddingSink):
    def __init__(self, client: redis.Redis, *, maxlen: int) -> None:
        self._r = client
        self._maxlen = maxlen

    def _stream_key(self, user_id: UUID, job_id: UUID) -> str:
        return f"ingest:{user_id}:{job_id}"

    async def emit(self, job_id: UUID, user_id: UUID, chunk: EmbeddedChunk) -> None:
        key = self._stream_key(user_id, job_id)
        fields: dict[str, str] = {
            "type": "chunk",
            "job_id": str(job_id),
            "user_id": str(user_id),
            "text": chunk.text,
            "embedding": json.dumps(list(chunk.embedding)),
            "metadata": json.dumps(chunk.metadata),
        }
        await self._r.xadd(key, fields, maxlen=self._maxlen, approximate=True)

    async def finalize(self, job_id: UUID, user_id: UUID, *, metadata: dict[str, Any] | None = None) -> None:
        key = self._stream_key(user_id, job_id)
        fields: dict[str, str] = {
            "type": "done",
            "job_id": str(job_id),
            "user_id": str(user_id),
            "metadata": json.dumps(metadata or {}),
        }
        await self._r.xadd(key, fields, maxlen=self._maxlen, approximate=True)

    async def clear(self, job_id: UUID, user_id: UUID) -> None:
        await self._r.delete(self._stream_key(user_id, job_id))

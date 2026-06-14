from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import redis.asyncio as redis

from rag_document_processor.application.ports.ingestion_result_reader import (
    IIngestionResultReader,
    IngestionChunkResult,
    IngestionStreamSnapshot,
)


def _parse_stream_entries(entries: list[tuple[str, dict[str, str]]]) -> IngestionStreamSnapshot:
    chunks: list[IngestionChunkResult] = []
    finalization: dict[str, Any] | None = None
    for fields in (entry[1] for entry in entries):
        entry_type = fields.get("type")
        if entry_type == "chunk":
            raw_embedding = json.loads(fields.get("embedding", "[]"))
            raw_metadata = json.loads(fields.get("metadata", "{}"))
            chunks.append(
                IngestionChunkResult(
                    index=len(chunks),
                    text=fields.get("text", ""),
                    embedding=tuple(float(x) for x in raw_embedding),
                    metadata=raw_metadata if isinstance(raw_metadata, dict) else {},
                )
            )
        elif entry_type == "done":
            raw = json.loads(fields.get("metadata", "{}"))
            finalization = raw if isinstance(raw, dict) else {}
    return IngestionStreamSnapshot(chunks=tuple(chunks), finalization_metadata=finalization)


class RedisStreamResultReader(IIngestionResultReader):
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    def _stream_key(self, job_id: UUID) -> str:
        return f"ingest:{job_id}"

    async def read(self, job_id: UUID) -> IngestionStreamSnapshot:
        key = self._stream_key(job_id)
        entries = await self._r.xrange(key)
        return _parse_stream_entries(entries)

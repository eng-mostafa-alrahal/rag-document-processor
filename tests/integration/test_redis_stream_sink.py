from __future__ import annotations

import json
import uuid

import pytest

try:
    import docker

    docker.from_env().ping()
except Exception as exc:  # pragma: no cover
    pytest.skip(f"Docker not available for testcontainers: {exc}", allow_module_level=True)

from testcontainers.redis import RedisContainer  # noqa: E402

import redis.asyncio as redis  # noqa: E402

from rag_document_processor.domain.value_objects.embedded_chunk import EmbeddedChunk  # noqa: E402
from rag_document_processor.infrastructure.sinks.redis_stream_sink import RedisStreamSink  # noqa: E402


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_stream_sink_writes_chunks() -> None:
    with RedisContainer("redis:7-alpine") as container:
        url = container.get_connection_url()
        client = redis.from_url(url, decode_responses=True)
        sink = RedisStreamSink(client, maxlen=1000)
        job_id = uuid.uuid4()
        await sink.clear(job_id)
        chunk = EmbeddedChunk("hello", (0.1, 0.2), {"a": 1})
        await sink.emit(job_id, chunk)
        await sink.finalize(job_id, metadata={"x": "y"})
        key = f"ingest:{job_id}"
        entries = await client.xrange(key)
        assert len(entries) >= 2
        fields = entries[0][1]
        assert fields["type"] == "chunk"
        assert json.loads(fields["embedding"]) == [0.1, 0.2]
        await client.aclose()

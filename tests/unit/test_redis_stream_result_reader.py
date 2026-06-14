from __future__ import annotations

import json

from rag_document_processor.infrastructure.sinks.redis_stream_result_reader import _parse_stream_entries


def test_parse_stream_entries_chunks_and_done() -> None:
    entries = [
        (
            "1-0",
            {
                "type": "chunk",
                "job_id": "00000000-0000-0000-0000-000000000001",
                "text": "hello",
                "embedding": json.dumps([0.1, 0.2]),
                "metadata": json.dumps({"section": 1}),
            },
        ),
        (
            "2-0",
            {
                "type": "chunk",
                "job_id": "00000000-0000-0000-0000-000000000001",
                "text": "world",
                "embedding": json.dumps([0.3]),
                "metadata": json.dumps({}),
            },
        ),
        (
            "3-0",
            {
                "type": "done",
                "job_id": "00000000-0000-0000-0000-000000000001",
                "metadata": json.dumps({"chunks": "2"}),
            },
        ),
    ]

    snapshot = _parse_stream_entries(entries)

    assert len(snapshot.chunks) == 2
    assert snapshot.chunks[0].index == 0
    assert snapshot.chunks[0].text == "hello"
    assert snapshot.chunks[0].embedding == (0.1, 0.2)
    assert snapshot.chunks[0].metadata == {"section": 1}
    assert snapshot.chunks[1].index == 1
    assert snapshot.finalization_metadata == {"chunks": "2"}


def test_parse_stream_entries_empty_stream() -> None:
    snapshot = _parse_stream_entries([])
    assert snapshot.chunks == ()
    assert snapshot.finalization_metadata is None

from __future__ import annotations

from rag_document_processor.infrastructure.pipelines.late_chunk_enhancer import (
    batch_chunks,
    merge_segments,
    simple_token_count,
)


def _wc(text: str) -> int:
    return simple_token_count(text)


def test_merge_combines_small_fragments_until_max() -> None:
    segments = ["one two", "three four", "five six", "seven eight"]
    # max 4 words per chunk, min 1 => pairs merge into 4-word chunks.
    out = merge_segments(segments, min_tokens=1, max_tokens=4, count_tokens=_wc)
    assert out == ["one two\nthree four", "five six\nseven eight"]


def test_merge_reduces_chunk_count() -> None:
    segments = [f"sentence number {i}." for i in range(30)]  # 3 words each
    # 15-word cap divides the 30x3 words evenly: 6 chunks, no trailing fold.
    out = merge_segments(segments, min_tokens=6, max_tokens=15, count_tokens=_wc)
    assert len(out) < len(segments)
    assert all(_wc(c) <= 15 for c in out)


def test_merge_respects_max_tokens() -> None:
    segments = ["a b c d e f"]  # 6 words, already over max
    out = merge_segments(segments, min_tokens=2, max_tokens=4, count_tokens=_wc)
    # A single oversized segment is kept as-is (its own chunk).
    assert out == ["a b c d e f"]


def test_merge_folds_trailing_small_chunk_back() -> None:
    # Last fragment alone is below min; it should fold into the previous chunk.
    segments = ["aa bb cc dd", "ee"]
    out = merge_segments(segments, min_tokens=3, max_tokens=4, count_tokens=_wc)
    assert out == ["aa bb cc dd\nee"]


def test_merge_empty_input() -> None:
    assert merge_segments([], min_tokens=1, max_tokens=10, count_tokens=_wc) == []
    assert merge_segments(["   ", ""], min_tokens=1, max_tokens=10, count_tokens=_wc) == []


def test_batch_packs_under_budget() -> None:
    chunks = ["a b c", "d e f", "g h i", "j k l"]  # 3 words each
    batches = batch_chunks(chunks, max_batch_tokens=6, count_tokens=_wc)
    assert batches == [["a b c", "d e f"], ["g h i", "j k l"]]


def test_batch_single_oversized_chunk_isolated() -> None:
    chunks = ["a b c d e", "f g"]  # first chunk 5 words > budget 4
    batches = batch_chunks(chunks, max_batch_tokens=4, count_tokens=_wc)
    assert batches == [["a b c d e"], ["f g"]]


def test_batch_all_fit_single_batch() -> None:
    chunks = ["a", "b", "c"]
    batches = batch_chunks(chunks, max_batch_tokens=100, count_tokens=_wc)
    assert batches == [["a", "b", "c"]]

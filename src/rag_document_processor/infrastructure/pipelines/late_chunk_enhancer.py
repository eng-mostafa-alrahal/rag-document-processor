"""Enhance + batch helpers for the late-chunking pipeline.

Late chunking only adds value when several related segments share a single Jina
request (the model attends across the whole ``input`` array, then returns one
vector per item). Two pure steps prepare segments for that:

1. ENHANCE (`merge_segments`): greedily merge adjacent fragments so we emit
   fewer, denser chunks (good for RAG) instead of one vector per sentence.
2. BATCH (`batch_chunks`): pack merged chunks into per-request groups that stay
   under the Jina token budget, so each API call keeps maximal shared context.

Token counting is injected as a callable so these functions stay pure and
testable; production wires a tiktoken-backed counter via `make_token_counter`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import lru_cache

TokenCounter = Callable[[str], int]

_WORD_RE = re.compile(r"\S+")


def simple_token_count(text: str) -> int:
    """Whitespace word count. Cheap, dependency-free fallback/default counter."""
    return len(_WORD_RE.findall(text))


@lru_cache(maxsize=8)
def _encoding(model: str):  # noqa: ANN202 - tiktoken type is internal
    import tiktoken

    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def make_token_counter(model: str = "gpt-4o-mini") -> TokenCounter:
    """Build a tiktoken-backed token counter (approximate for Jina, fast)."""
    enc = _encoding(model)

    def _count(text: str) -> int:
        return len(enc.encode(text))

    return _count


def merge_segments(
    segments: list[str],
    *,
    min_tokens: int,
    max_tokens: int,
    count_tokens: TokenCounter = simple_token_count,
    join_with: str = "\n",
) -> list[str]:
    """Merge adjacent fragments into denser chunks.

    Greedy rule (no similarity model):
      - Accumulate segments into the current chunk while staying <= ``max_tokens``.
      - When the next segment would overflow ``max_tokens``:
          * if the current chunk already has >= ``min_tokens`` tokens, finalize it
            and start a new chunk with the next segment;
          * otherwise force-append the segment anyway (avoid tiny fragments), then
            finalize and start fresh.
      - A trailing chunk below ``min_tokens`` is merged back into the previous
        chunk so we never emit a tiny dangling fragment (unless it's the only one).

    A single segment larger than ``max_tokens`` is kept as its own chunk.
    """
    clean = [s.strip() for s in segments if s and s.strip()]
    if not clean:
        return []
    if max_tokens < 1:
        raise ValueError("max_tokens must be >= 1")
    if min_tokens < 0:
        raise ValueError("min_tokens must be >= 0")

    chunks: list[str] = []
    current = clean[0]
    current_tokens = count_tokens(current)

    for seg in clean[1:]:
        seg_tokens = count_tokens(seg)
        if current_tokens + seg_tokens <= max_tokens:
            current = f"{current}{join_with}{seg}"
            current_tokens += seg_tokens
            continue
        if current_tokens >= min_tokens:
            chunks.append(current)
            current = seg
            current_tokens = seg_tokens
        else:
            # Current chunk is too small to stand alone: force-merge to avoid a
            # tiny fragment, then finalize.
            current = f"{current}{join_with}{seg}"
            chunks.append(current)
            current = ""
            current_tokens = 0

    if current:
        chunks.append(current)

    # Fold a trailing sub-min chunk back into its predecessor.
    if len(chunks) >= 2 and count_tokens(chunks[-1]) < min_tokens:
        tail = chunks.pop()
        chunks[-1] = f"{chunks[-1]}{join_with}{tail}"

    return chunks


def batch_chunks(
    chunks: list[str],
    *,
    max_batch_tokens: int,
    count_tokens: TokenCounter = simple_token_count,
) -> list[list[str]]:
    """Pack chunks into batches whose total token count stays <= ``max_batch_tokens``.

    Each batch becomes one Jina ``late_chunking=true`` request, so larger batches
    mean more shared context. A single chunk larger than the budget is placed in
    its own batch (it must still be embedded).
    """
    if max_batch_tokens < 1:
        raise ValueError("max_batch_tokens must be >= 1")

    batches: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0

    for chunk in chunks:
        if not chunk.strip():
            continue
        tokens = count_tokens(chunk)
        if current and current_tokens + tokens > max_batch_tokens:
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(chunk)
        current_tokens += tokens

    if current:
        batches.append(current)

    return batches

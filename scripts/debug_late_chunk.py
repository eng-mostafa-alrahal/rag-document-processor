"""Run the late-chunking pipeline fully offline (no Docker, no API, no Celery).

No Postgres, Redis, or Jina required in the default (fake embedder) mode.

Breakpoints:
  - infrastructure/pipelines/embedding_pipelines.py (LateChunkingPipeline)
  - infrastructure/pipelines/late_chunk_enhancer.py (merge + batch)
  - infrastructure/splitters/macro_splitters.py

Usage (from repo root):

    uv run python scripts/debug_late_chunk.py
    uv run python scripts/debug_late_chunk.py --text "Your document text here."
    uv run python scripts/debug_late_chunk.py --file ./sample.txt
    uv run python scripts/debug_late_chunk.py --file ./sample.pdf
    uv run python scripts/debug_late_chunk.py --jina   # real Jina (needs JINA_API_KEY)

Or in Cursor: Run and Debug → "Debug: late-chunk (no Docker)".
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Allow `uv run python scripts/...` without installing the package globally.
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Offline-friendly defaults before Settings is loaded (no Docker Postgres/Redis).
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("STORAGE_BACKEND", "local")


import httpx  # noqa: E402

from rag_document_processor.application.ports.embedding_pipeline import IEmbedder  # noqa: E402
from rag_document_processor.core.config import Settings  # noqa: E402
from rag_document_processor.core.ingest_embedding_options import MacroKind  # noqa: E402
from rag_document_processor.core.pipeline_factory import build_macro_splitter  # noqa: E402
from rag_document_processor.infrastructure.pipelines.embedding_pipelines import (  # noqa: E402
    LateChunkingPipeline,
)
from rag_document_processor.infrastructure.pipelines.late_chunk_enhancer import (  # noqa: E402
    make_token_counter,
)


class _FakeEmbedder(IEmbedder):
    """No Jina calls — use when you only want to debug split/merge/batch."""

    name = "fake"

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    async def embed_texts(
        self,
        texts: list[str],
        *,
        late_chunking: bool = False,
        dimensions: int | None = None,
    ) -> list[tuple[float, ...]]:
        _ = late_chunking, dimensions
        self.batches.append(list(texts))
        return [tuple(float(j) for j in range(8)) for _ in texts]


_DEFAULT_TEXT = (
    "Revenue grew twelve percent year over year. "
    "The product team shipped three major features. "
    "Customer retention improved in enterprise accounts. "
    "Hiring focused on platform engineering and ML. "
) * 8


def _load_settings() -> Settings:
    """Load Settings without requiring a live database/Redis."""
    # Clear cached settings so ENV overrides above take effect when re-run under debugger.
    from rag_document_processor.core.config import get_settings

    get_settings.cache_clear()
    return get_settings()


async def _load_text(*, text: str | None, file_path: Path | None) -> str:
    if text is not None:
        return text
    if file_path is None:
        return _DEFAULT_TEXT

    data = file_path.read_bytes()
    suffix = file_path.suffix.lower()
    if suffix in (".txt", ".md") or not suffix:
        return data.decode("utf-8", errors="replace")

    # PDF/DOCX: local llama-index readers (no Docker). Cloud parse is optional.
    settings = _load_settings()
    from rag_document_processor.core.container import _build_text_extractor

    ctype = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(suffix, "application/octet-stream")
    extractor = _build_text_extractor(settings)
    return await extractor.extract(
        data, content_type=ctype, filename=file_path.name, llama_parse_tier=None
    )


def _build_offline_pipeline(
    settings: Settings,
    *,
    macro: MacroKind,
    min_tokens: int,
    max_tokens: int,
    batch_tokens: int,
    use_jina: bool,
    httpx_client: httpx.AsyncClient,
) -> tuple[LateChunkingPipeline, _FakeEmbedder | None, str]:
    macro_splitter = build_macro_splitter(settings, macro)

    if use_jina:
        if not settings.jina_api_key:
            raise SystemExit(
                "JINA_API_KEY is required for --jina. "
                "Omit --jina to debug split/merge/batch with a fake embedder (no Docker, no API key)."
            )
        from rag_document_processor.infrastructure.embedders.jina_embedder import JinaEmbedder

        embedder = JinaEmbedder(
            api_key=settings.jina_api_key,
            model=settings.jina_embedding_model,
            client=httpx_client,
        )
        pipe = LateChunkingPipeline(
            macro_splitter=macro_splitter,
            embedder=embedder,
            min_tokens=min_tokens,
            max_tokens=max_tokens,
            batch_tokens=batch_tokens,
            count_tokens=make_token_counter(),
        )
        return pipe, None, f"jina ({settings.jina_embedding_model})"

    fake = _FakeEmbedder()
    pipe = LateChunkingPipeline(
        macro_splitter=macro_splitter,
        embedder=fake,
        min_tokens=min_tokens,
        max_tokens=max_tokens,
        batch_tokens=batch_tokens,
        count_tokens=make_token_counter(),
    )
    return pipe, fake, "fake (offline — no Jina / Docker)"


async def _run(
    *,
    text: str | None,
    file_path: Path | None,
    use_jina: bool,
    min_tokens: int | None,
    max_tokens: int | None,
    batch_tokens: int | None,
    macro: str,
) -> int:
    settings = _load_settings()
    lc_min = min_tokens if min_tokens is not None else settings.late_chunk_min_tokens
    lc_max = max_tokens if max_tokens is not None else settings.late_chunk_max_tokens
    lc_batch = batch_tokens if batch_tokens is not None else settings.late_chunk_batch_tokens
    if lc_min > lc_max:
        raise SystemExit(f"min_tokens ({lc_min}) cannot exceed max_tokens ({lc_max})")

    raw = await _load_text(text=text, file_path=file_path)
    macro_kind: MacroKind = macro  # type: ignore[assignment]

    async with httpx.AsyncClient() as client:
        pipeline, fake_embedder, embedder_label = _build_offline_pipeline(
            settings,
            macro=macro_kind,
            min_tokens=lc_min,
            max_tokens=lc_max,
            batch_tokens=lc_batch,
            use_jina=use_jina,
            httpx_client=client,
        )

        print("--- late-chunk debug (no Docker) ---")
        print(f"embedder:        {embedder_label}")
        print(f"macro_splitter:  {macro}")
        print(f"min/max tokens:  {lc_min} / {lc_max}")
        print(f"batch budget:    {lc_batch}")
        print(f"input chars:     {len(raw)}")
        print()

        chunks = [c async for c in pipeline.process(raw, metadata={"debug": True})]
        print(f"chunks emitted:  {len(chunks)}")
        for i, c in enumerate(chunks):
            tc = c.metadata.get("token_count", "?")
            bi = c.metadata.get("batch_index", "?")
            preview = c.text.replace("\n", " ")[:100]
            print(f"  [{i}] batch={bi} tokens={tc} | {preview!r}")

        if fake_embedder is not None:
            print()
            print(f"jina batches:    {len(fake_embedder.batches)} (would be late_chunking=true)")
            for bi, batch in enumerate(fake_embedder.batches):
                print(f"  batch {bi}: {len(batch)} chunk(s) sharing one context window")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Debug late-chunking offline (no Docker / Postgres / Redis)."
    )
    parser.add_argument("--text", help="Inline document text (default: built-in sample).")
    parser.add_argument("--file", type=Path, help="PDF/DOCX/txt/md path to extract then chunk.")
    parser.add_argument(
        "--jina",
        action="store_true",
        help="Call real Jina API (requires JINA_API_KEY). Default is fully offline fake embedder.",
    )
    parser.add_argument("--min-tokens", type=int, default=None, help="Override LATE_CHUNK_MIN_TOKENS.")
    parser.add_argument("--max-tokens", type=int, default=None, help="Override LATE_CHUNK_MAX_TOKENS.")
    parser.add_argument(
        "--batch-tokens", type=int, default=None, help="Override LATE_CHUNK_BATCH_TOKENS."
    )
    parser.add_argument(
        "--macro",
        choices=("recursive", "semantic", "token_aware"),
        default="recursive",
        help="Macro splitter (default: recursive).",
    )
    args = parser.parse_args()
    return asyncio.run(
        _run(
            text=args.text,
            file_path=args.file,
            use_jina=args.jina,
            min_tokens=args.min_tokens,
            max_tokens=args.max_tokens,
            batch_tokens=args.batch_tokens,
            macro=args.macro,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

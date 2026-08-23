# Pipelines — detailed maps

This document describes every **embedding pipeline**, **macro splitter**, and **extraction** path used by the Celery worker. For an interactive version, open the Cursor canvas `pipeline-diagrams.canvas.tsx` beside chat.

Primary code:

| Area | Path |
|------|------|
| Factory | `core/pipeline_factory.py` |
| Pipelines | `infrastructure/pipelines/embedding_pipelines.py` |
| Late enhance/batch | `infrastructure/pipelines/late_chunk_enhancer.py` |
| Macro splitters | `infrastructure/splitters/macro_splitters.py` |
| Classic chunker | `infrastructure/splitters/sentence_chunker.py` |
| Option resolve | `core/ingest_embedding_options.py` |
| Worker orchestration | `application/use_cases/ingestion/process_job.py` |
| Extraction | `infrastructure/extraction/` |
| Sink | `infrastructure/sinks/redis_stream_sink.py` |

---

## 1. Worker overview (end-to-end)

```mermaid
flowchart TD
  A[API submit<br/>file / url / text] --> B[Persist job in Postgres<br/>status = queued]
  B --> C[Celery enqueue]
  C --> D[ProcessIngestionJobUseCase]
  D --> E[status = PROCESSING<br/>RedisStreamSink.clear]
  E --> F{source_kind}
  F -->|TEXT| G[texts_from_source_text<br/>JSON array or legacy string]
  F -->|URL| H[IUrlFetcher.fetch<br/>→ ITextExtractor.extract]
  F -->|FILE| I[IBlobStorage.get_bytes<br/>→ ITextExtractor.extract]
  G --> J[resolve_ingest_embedding_options]
  H --> J
  I --> J
  J --> K[build_embedding_pipeline]
  K --> L[For each text segment:<br/>pipeline.process → sink.emit]
  L --> M[sink.finalize type=done]
  M --> N[Job COMPLETED<br/>chunks_emitted += N]
  D -.->|on error| X[Job FAILED<br/>error_message]
```

**Per-chunk Redis fields** (`ingest:{job_id}` stream): `type=chunk`, `text`, `embedding` (JSON array), `metadata` (JSON). Finalize adds `type=done` with `{"chunks": "N"}`.

**Job-level metadata** attached before `process` (and merged onto each chunk):

- Always: `job_id`, `source_kind`, `embedding_pipeline`, `macro_splitter`, `embedder`, `text_index`
- Multi-text ingest: `text_count`
- Late chunking: `late_chunk_min_tokens`, `late_chunk_max_tokens`, `late_chunk_batch_tokens`
- Pipeline adds: `chunk_index`, `pipeline`, optional `embedding_dimensions`; late also `batch_index`, `token_count`

---

## 2. `chunk_then_embed`

**Default** (`EMBEDDING_PIPELINE=chunk_then_embed`). Independent chunk → embed. Supports **OpenAI or Jina**.

```mermaid
flowchart LR
  T[Raw text] --> C[RecursiveSentenceChunker<br/>chunk_size=1500 · overlap=150]
  C --> S[Segment N]
  S --> E["embed_texts([seg])<br/>late_chunking=false"]
  E --> O[EmbeddedChunk<br/>chunk_index=N]
```

| Piece | Detail |
|-------|--------|
| Class | `ChunkThenEmbedPipeline` |
| Chunker | `RecursiveSentenceChunker` (LlamaIndex `SentenceSplitter`) |
| Macro splitter | **Not used** (factory only builds macros for `late_chunking`) |
| Embedder | `OpenAIEmbedder` if `resolved.embedder == "openai"`, else `JinaEmbedder` |
| API pattern | **One embed call per chunk** (sequential `await`) |
| Late-chunk token knobs | Ignored |

**When to use:** OpenAI-only stacks; simple RAG; predictable overlapping windows; lowest operational complexity.

---

## 3. `late_chunking`

**Jina-only.** Full text → **macro splitter** produces chunk text (recursive / token_aware / semantic, with small overlap) → **ENHANCE** enforces `min_tokens`..`max_tokens` → **BATCH** packs under the Jina request budget → one `late_chunking=true` embed call per batch.

```mermaid
flowchart TD
  T[Raw text] --> M["IMacroSplitter.split<br/>recursive / token_aware / semantic<br/>target ≈ max_tokens · overlap 128"]
  M --> D[_dedupe_adjacent<br/>drop overlap duplicates]
  D --> E["enhance_chunks ENHANCE<br/>split if &gt; max · merge if &lt; min"]
  E --> B["batch_chunks BATCH<br/>≤ batch_tokens per request"]
  B --> J["JinaEmbedder.embed_texts<br/>late_chunking=true"]
  J --> O[Yield EmbeddedChunk per item<br/>chunk_index · batch_index · token_count]
```

### 3.1 Macro split (chunk text)

Each macro splitter yields **chunk candidates** sized near `late_chunk_max_tokens` (default 512), with **128-token overlap** between consecutive chunks (deduped before enhance):

| Splitter | Mechanism |
|----------|-----------|
| `recursive` | LlamaIndex `SentenceSplitter`; char budget ≈ `max_tokens × 4` |
| `token_aware` | tiktoken sliding window; `max_tokens` + 128 overlap |
| `semantic` | OpenAI embedding breakpoints (topic shifts); variable size → enhance normalizes |

### 3.2 ENHANCE (`enhance_chunks`)

Normalizes macro output to `min_tokens`..`max_tokens`:

1. **Sub-split** any macro chunk above `max_tokens` (sentence-aware).
2. **Dedupe** consecutive duplicates from macro overlap.
3. **Merge** adjacent fragments below `min_tokens` while staying ≤ `max_tokens`.

Tokens counted via `make_token_counter()` (tiktoken `gpt-4o-mini` / `cl100k_base`).

### 3.3 BATCH (`batch_chunks`) → Jina

Pack enhanced chunks so total tokens ≤ `LATE_CHUNK_BATCH_TOKENS` (default **7000**).

- **Each batch = one** `POST https://api.jina.ai/v1/embeddings` with `late_chunking=true` and `input = [chunk strings in that batch]`.
- Chunks in the **same** batch share late-chunking context; chunks in **different** batches do not.
- Oversized single chunks get their own batch (still one API call).
- Batching is a **client-side** budget to stay under the model context window (e.g. ~8K for `jina-embeddings-v3`); Jina does not require a fixed batch count.

### 3.4 Defaults and overrides

| Knob | Env default | Per-job override? |
|------|-------------|-------------------|
| `late_chunk_min_tokens` | `LATE_CHUNK_MIN_TOKENS` = 256 | Yes |
| `late_chunk_max_tokens` | `LATE_CHUNK_MAX_TOKENS` = 512 | Yes (also sizes recursive / token_aware macro windows) |
| `late_chunk_batch_tokens` | `LATE_CHUNK_BATCH_TOKENS` = 7000 | No (env only) |
| Macro overlap | 128 tokens | Fixed in factory (`DEFAULT_MACRO_OVERLAP_TOKENS`) |

**Hard rules at resolve:** `embedder_provider=openai` → **422**; `JINA_API_KEY` required; `1 ≤ min ≤ max ≤ 8192`.

**When to use:** Context-aware embeddings; fewer denser RAG chunks (raise min/max); Jina is available.

---

## 4. Macro splitters (late_chunking only)

Factory: `build_macro_splitter(settings, macro, max_tokens=late_chunk_max_tokens, overlap_tokens=128)`.

```mermaid
flowchart TD
  R[Resolved macro_splitter] --> Q{kind}
  Q -->|recursive| Rec["RecursiveMacroSplitter<br/>SentenceSplitter · ≈ max_tokens chars · overlap 128"]
  Q -->|token_aware| Tok["TokenAwareMacroSplitter<br/>max_tokens + overlap 128"]
  Q -->|semantic| Sem{OPENAI_API_KEY?}
  Sem -->|yes| SemY[SemanticMacroSplitter<br/>OpenAIEmbedding + SemanticSplitterNodeParser]
  Sem -->|no| Rec
```

| Name | Mechanism | Notes |
|------|-----------|--------|
| `recursive` | LlamaIndex `SentenceSplitter` sized from `late_chunk_max_tokens` | **Default**; also silent fallback for semantic without key |
| `token_aware` | Sliding tiktoken window | `max_tokens = late_chunk_max_tokens`, overlap 128 |
| `semantic` | `SemanticSplitterNodeParser` + `text-embedding-3-small` | Topic-based breaks; enhance enforces min/max after |

Overlap from recursive/token windows can produce duplicate adjacent chunks; late pipeline removes them with `_dedupe_adjacent` before enhance.

---

## 5. Extraction (upstream of both pipelines)

```mermaid
flowchart TD
  B[Bytes + content_type + filename] --> P{plain / markdown?}
  P -->|yes| U[UTF-8 decode]
  P -->|no| C{PDF/DOCX and LLAMA_CLOUD_API_KEY?}
  C -->|yes| L[LlamaCloudParseExtractor<br/>parsing.parse tier + expand]
  C -->|no| F[LlamaIndexTextExtractor fallback<br/>PDFReader / DocxReader / …]
  L --> T[Plain text]
  F --> T
  U --> T
  T --> Pipe[Embedding pipeline]
```

| Tier | `expand` | Notes |
|------|----------|--------|
| `fast` | `["text"]` | Markdown expand rejected by LlamaCloud |
| `cost_effective` / `agentic` / `agentic_plus` | `["markdown","text"]` | Prefer markdown pages (+ header/footer) |

Per-job `llama_parse_tier` overrides `LLAMA_PARSE_TIER` (default `agentic`).

---

## 6. Factory decision tree

```mermaid
flowchart TD
  O[ResolvedIngestEmbeddingOptions] --> P{embedding_pipeline}
  P -->|late_chunking| M["build_macro_splitter<br/>max=late_chunk_max_tokens · overlap 128"]
  M --> LC[LateChunkingPipeline<br/>+ JinaEmbedder<br/>+ enhance + batch]
  P -->|chunk_then_embed| CT[ChunkThenEmbedPipeline<br/>+ RecursiveSentenceChunker]
  CT --> E{embedder}
  E -->|openai| OA[OpenAIEmbedder]
  E -->|jina| JI[JinaEmbedder]
```

---

## 7. Choose quickly

| Need | Prefer |
|------|--------|
| OpenAI embeddings only | `chunk_then_embed` |
| Shared context inside vectors | `late_chunking` |
| Fewer denser chunks | `late_chunking` + raise `late_chunk_min/max_tokens` |
| Hard token window on long docs | `late_chunking` + `macro_splitter=token_aware` |
| Topic-ish macro breaks | `late_chunking` + `macro_splitter=semantic` (+ OpenAI key) |
| Simplest default | `chunk_then_embed` |

Client-facing field reference: [API_INTEGRATION.md](./API_INTEGRATION.md). Onboarding overview: [ONBOARDING.md](./ONBOARDING.md).

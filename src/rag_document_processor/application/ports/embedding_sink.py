from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from rag_document_processor.domain.value_objects.embedded_chunk import EmbeddedChunk


class IEmbeddingSink(Protocol):
    async def emit(self, job_id: UUID, chunk: EmbeddedChunk) -> None: ...

    async def finalize(self, job_id: UUID, *, metadata: dict[str, Any] | None = None) -> None: ...

    async def clear(self, job_id: UUID) -> None:
        """Remove any staged stream for this job (e.g. before reprocessing)."""

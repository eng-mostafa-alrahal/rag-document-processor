from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class IngestionChunkResult:
    index: int
    text: str
    embedding: tuple[float, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IngestionStreamSnapshot:
    chunks: tuple[IngestionChunkResult, ...]
    finalization_metadata: dict[str, Any] | None


class IIngestionResultReader(Protocol):
    async def read(self, job_id: UUID) -> IngestionStreamSnapshot: ...

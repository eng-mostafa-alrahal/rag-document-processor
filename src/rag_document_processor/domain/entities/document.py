from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Document:
    """Logical document produced after extraction (before chunking)."""

    job_id: UUID
    text: str
    content_type: str | None
    title: str | None = None

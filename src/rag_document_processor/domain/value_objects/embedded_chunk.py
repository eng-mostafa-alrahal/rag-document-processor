from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    text: str
    embedding: tuple[float, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

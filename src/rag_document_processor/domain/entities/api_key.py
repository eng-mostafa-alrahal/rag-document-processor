from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ApiKey:
    """A client API key. The raw secret is never stored or returned here.

    Only `key_prefix` (a short, non-secret identifier) is persisted alongside a
    one-way hash of the full key used for verification.
    """

    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None

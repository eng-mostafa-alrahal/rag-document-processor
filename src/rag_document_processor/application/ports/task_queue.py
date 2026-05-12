from __future__ import annotations

from typing import Protocol
from uuid import UUID


class ITaskQueue(Protocol):
    async def enqueue_process_job(self, job_id: UUID) -> None: ...
